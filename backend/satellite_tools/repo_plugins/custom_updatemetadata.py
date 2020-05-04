from rpmUtils.arch import ArchStorage

class UpdateMetadata(object):

    """
    The root update metadata object.
    """

    def __init__(self, repos=[], logger=None, vlogger=None):
        self._notices = {}
        self._cache = {}    # a pkg nvr => notice cache for quick lookups
        self._no_cache = {}    # a pkg name only => notice list
        self._repos = []    # list of repo ids that we've parsed

#        self._logger  = logger
        self._vlogger = vlogger

        for repo in repos:
            try: # attempt to grab the updateinfo.xml.gz from the repodata
                self.add(repo)
            except Errors.RepoMDError:
                continue # No metadata found for this repo

#        self.arch_storage = ArchStorage()
#        self.archlist = self.arch_storage.archlist

    def get_notices(self, name=None):
        """ Return all notices. """
        if name is None:
            return self._notices.values()
        return name in self._no_cache and self._no_cache[name] or []

    notices = property(get_notices)

    def get_notice(self, nvr):
        """
        Retrieve an update notice for a given (name, version, release) string
        or tuple.
        """
        if type(nvr) in (type([]), type(())):
            nvr = '-'.join(nvr)
        return self._cache.get(nvr) or None

    #  The problem with the above "get_notice" is that not everyone updates
    # daily. So if you are at pkg-1, pkg-2 has a security notice, and pkg-3
    # has a BZ fix notice. All you can see is the BZ notice for the new "pkg-3"
    # with the above.
    #  So now instead you lookup based on the _installed_ pkg.pkgtup, and get
    # two notices, in order: [(pkgtup-3, notice), (pkgtup-2, notice)]
    # the reason for the sorting order is that the first match will give you
    # the minimum pkg you need to move to.
    def get_applicable_notices(self, pkgtup):
        """
        Retrieve any update notices which are newer than a
        given std. pkgtup (name, arch, epoch, version, release) tuple.
        Returns: list of (pkgtup, notice) that are newer than the given pkgtup,
                 in the order of newest pkgtups first.
        """
        oldpkgtup = pkgtup
        name = oldpkgtup[0]
        arch = oldpkgtup[1]
        ret = []
        other_arch_list = []
        notices = set()
        for notice in self.get_notices(name):
            for upkg in notice['pkglist']:
                for pkg in upkg['packages']:
                    other_arch = False
                    if pkg['name'] != name or pkg['arch'] != arch:
                        if (notice not in notices and pkg['name'] == name and pkg['arch'] in self.archlist):
                            other_arch = True
                        else:
                            continue
                    pkgtup = (pkg['name'], pkg['arch'], pkg['epoch'] or '0',
                              pkg['version'], pkg['release'])
                    if _rpm_tup_vercmp(pkgtup, oldpkgtup) <= 0:
                        continue
                    if other_arch:
                        other_arch_list.append((pkgtup, notice))
                    else:
                        ret.append((pkgtup, notice))
                        notices.add(notice)
        for pkgtup, notice in other_arch_list:
            if notice not in notices:
                ret.append((pkgtup, notice))
        ret.sort(cmp=_rpm_tup_vercmp, key=lambda x: x[0], reverse=True)
        return ret

    def add_notice(self, un):
        """ Add an UpdateNotice object. This should be fully populated with
            data, esp. update_id and pkglist/packages. """
        if not un or not un["update_id"]:
            return False

        #  This is "special", the main thing we want to deal with here is
        # having one errata that has multiple packages in it rpmA and rpmB, but
        # the packages are in repos. repoA and repoB. So instead of doing a
        # single errata pointing to both rpmA and rpmB and put the same thing
        # in both repodata (which is legal, and works fine) people want to have
        # just the packages from repoA in the repodata for repoA and vice versa.
        if un['update_id'] in self._notices:
            oun = self._notices[un['update_id']]
            if oun != un:
                return False

            # Ok, main parts of errata are the same, so now merge references:
            seen = set()
            for ref in oun['references']:
                seen.add(ref['id'])
            for ref in un['references']:
                if ref['id'] in seen:
                    continue
                seen.add(ref['id'])
                oun['references'].append(ref)

            # ...and pkglist (this assumes that a pkglist name XYZ is the same):
            seen = set()
            for pkg in oun['pkglist']:
                seen.add(pkg['name'])
            for pkg in un['pkglist']:
                if pkg['name'] in seen:
                    continue
                seen.add(pkg['name'])
                oun['pkglist'].append(pkg)

            un = oun

        self._notices[un['update_id']] = un
        for pkg in un['pkglist']:
            for filedata in pkg['packages']:
                self._cache['%s-%s-%s' % (filedata['name'],
                                          filedata['version'],
                                          filedata['release'])] = un
                no = self._no_cache.setdefault(filedata['name'], set())
                no.add(un)

        return True

    def add(self, obj, mdtype='updateinfo'):
        """ Parse a metadata from a given YumRepository, file, or filename. """

        def _rid(repoid, fmt=_('(from %s)'), unknown=_("<unknown>")):
            if not repoid:
                repoid = unknown
            return fmt % repoid

        if not obj:
            raise UpdateNoticeException
        repoid = None
        if type(obj) in (type(''), type(u'')):
            unfile = decompress(obj)
            infile = open(unfile, 'rt')

        elif isinstance(obj, YumRepository):
            if obj.id not in self._repos:
                repoid = obj.id
                self._repos.append(obj.id)
                md = obj.retrieveMD(mdtype)
                if not md:
                    raise UpdateNoticeException()
                unfile = repo_gen_decompress(md, 'updateinfo.xml')
                infile = open(unfile, 'rt')
        elif isinstance(obj, FakeRepository):
            raise Errors.RepoMDError, "No updateinfo for local pkg"
        else:   # obj is a file object
            infile = obj

        have_dup = False
        for event, elem in safe_iterparse(infile, logger=self._logger):
            if elem.tag == 'update':
                try:
                    un = UpdateNotice(elem)
                except UpdateNoticeException, e:
                    msg = _("An update notice %s is broken, skipping.") % _rid(repoid)
                    if self._vlogger:
                        self._vlogger.log(logginglevels.DEBUG_1, "%s", msg)
                    else:
                        print >> sys.stderr, msg
                    continue

                if not self.add_notice(un):
                    msg = _("Update notice %s %s is broken, or a bad duplicate, skipping.") % (un['update_id'], _rid(repoid))
                    if not have_dup:
                        msg += _('\nYou should report this problem to the owner of the %s repository.') % _rid(repoid, "%s")
                    have_dup = True
                    if self._vlogger:
                        self._vlogger.warn("%s", msg)
                    else:
                        print >> sys.stderr, msg

    def __unicode__(self):
        ret = u''
        for notice in self.notices:
            ret += unicode(notice)
        return ret
    def __str__(self):
        return to_utf8(self.__unicode__())

    def xml(self, fileobj=None):
        msg = """<?xml version="1.0"?>\n<updates>"""
        if fileobj:
            fileobj.write(msg)

        for notice in self._notices.values():
            if fileobj:
                fileobj.write(notice.xml())
            else:
                msg += notice.xml()

        end = """</updates>\n"""
        if fileobj:
            fileobj.write(end)
        else:
            msg += end

        if fileobj:
            return

        return msg


def main():
    """ update_md test function. """
    import yum.misc

    yum.misc.setup_locale()
    def usage():
        print >> sys.stderr, "Usage: %s <update metadata> ..." % sys.argv[0]
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()

    try:
        print sys.argv[1]
        um = UpdateMetadata()
        for srcfile in sys.argv[1:]:
            um.add(srcfile)
        print unicode(um)
    except IOError:
        print >> sys.stderr, "%s: No such file:\'%s\'" % (sys.argv[0],
                                                          sys.argv[1:])
        usage()

if __name__ == '__main__':
    main()
