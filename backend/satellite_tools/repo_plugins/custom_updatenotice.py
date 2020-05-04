#!/usr/bin/python2 -t
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2005 Duke University 
#
# Seth Vidal <skvidal@linux.duke.edu>
# Luke Macken <lmacken@redhat.com>

"""
Update metadata (updateinfo.xml) parsing.
"""

import rpmUtils.miscutils
from rpmUtils.arch import ArchStorage


def safe_iterparse(filename, logger=None):
    """ Works like iterparse, but hides XML errors (prints a warning). """
    try:
        for event, elem in iterparse(filename):
            yield event, elem
    except SyntaxError: # Bad XML
        if logger:
            logger.critical(_("Updateinfo file is not valid XML: %s"), filename)
        else:
            print >> sys.stderr, "Updateinfo file is not valid XML:", filename

class UpdateNoticeException(Exception):
    """ An exception thrown for bad UpdateNotice data. """
    pass


class UpdateNotice(object):

    """
    A single update notice (for instance, a security fix).
    """

    def __init__(self, elem=None):
        self._md = {
            'from'             : '',
            'type'             : '',
            'title'            : '',
            'release'          : '',
            'status'           : '',
            'version'          : '',
            'pushcount'        : '',
            'update_id'        : '',
            'issued'           : '',
            'updated'          : '',
            'description'      : '',
            'rights'           : '',
            'severity'         : '',
            'summary'          : '',
            'solution'         : '',
            'references'       : [],
            'pkglist'          : [],
            'reboot_suggested' : False
        }

        if elem:
            self._parse(elem)

    def __getitem__(self, item):
        """ Allows scriptable metadata access (ie: un['update_id']). """
        if type(item) is int:
            return sorted(self._md)[item]
        ret = self._md.get(item)
        if ret == '':
            ret = None
        return ret

    def __contains__(self, item):
        """ Allows quick tests for foo in blah. """
        return item in self._md

    def __setitem__(self, item, val):
        self._md[item] = val

    def __eq__(self, other):
        #  Tests to see if it's "the same data", which means that the
        # packages can be different (see add_notice).

        if not other or not hasattr(other, '_md'):
            return False

        for data in ('type', 'update_id', 'status', 'rights',
                     'severity', 'release',
                     'issued', 'updated', 'version', 'pushcount',
                     'from', 'title', 'summary', 'description', 'solution'):
            if data == 'status': # FIXME: See below...
                continue
            if self._md[data] != other._md[data]:
                return False
        # FIXME: Massive hack, Fedora is really broken and gives status=stable
        # and status=testing for updateinfo notices, just depending on which
        # repo. they come from.
        data = 'status'
        if self._md[data] != other._md[data]:
            if self._md[data]  not in ('stable', 'testing'):
                return False
            if other._md[data] not in ('stable', 'testing'):
                return False
            # They are both really "stable" ...
            self._md[data]  = 'stable'
            other._md[data] = 'stable'

        return True

    def __ne__(self, other):
        return not (self == other)

    def text(self, skip_data=('files', 'summary', 'rights', 'solution')):
        head = """
===============================================================================
  %(title)s
===============================================================================
  Update ID : %(update_id)s
    Release : %(release)s
       Type : %(type)s
     Status : %(status)s
     Issued : %(issued)s
""" % self._md

        if self._md['updated'] and self._md['updated'] != self._md['issued']:
            head += "    Updated : %s" % self._md['updated']

        # Add our bugzilla references
        bzs = filter(lambda r: r['type'] == 'bugzilla', self._md['references'])
        if len(bzs) and 'bugs' not in skip_data:
            buglist = "       Bugs :"
            for bz in bzs:
                buglist += " %s%s\n\t    :" % (bz['id'], 'title' in bz
                                               and ' - %s' % bz['title'] or '')
            head += buglist[: - 1].rstrip() + '\n'

        # Add our CVE references
        cves = filter(lambda r: r['type'] == 'cve', self._md['references'])
        if len(cves) and 'cves' not in skip_data:
            cvelist = "       CVEs :"
            for cve in cves:
                cvelist += " %s\n\t    :" % cve['id']
            head += cvelist[: - 1].rstrip() + '\n'

        if self._md['summary'] and 'summary' not in skip_data:
            data = utf8_text_wrap(self._md['summary'], width=64,
                                  subsequent_indent=' ' * 12 + ': ')
            head += "    Summary : %s\n" % '\n'.join(data)

        if self._md['description'] and 'description' not in skip_data:
            desc = utf8_text_wrap(self._md['description'], width=64,
                                  subsequent_indent=' ' * 12 + ': ')
            head += "Description : %s\n" % '\n'.join(desc)

        if self._md['solution'] and 'solution' not in skip_data:
            data = utf8_text_wrap(self._md['solution'], width=64,
                                  subsequent_indent=' ' * 12 + ': ')
            head += "   Solution : %s\n" % '\n'.join(data)

        if self._md['rights'] and 'rights' not in skip_data:
            data = utf8_text_wrap(self._md['rights'], width=64,
                                  subsequent_indent=' ' * 12 + ': ')
            head += "     Rights : %s\n" % '\n'.join(data)

        if self._md['severity'] and 'severity' not in skip_data:
            data = utf8_text_wrap(self._md['severity'], width=64,
                                  subsequent_indent=' ' * 12 + ': ')
            head += "   Severity : %s\n" % '\n'.join(data)

        if 'files' in skip_data:
            return head[:-1] # chop the last '\n'

        #  Get a list of arches we care about:
        #XXX ARCH CHANGE - what happens here if we set the arch - we need to
        # pass this in, perhaps
        arches = set(rpmUtils.arch.getArchList())

        filelist = "      Files :"
        for pkg in self._md['pkglist']:
            for file in pkg['packages']:
                if file['arch'] not in arches:
                    continue
                filelist += " %s\n\t    :" % file['filename']
        head += filelist[: - 1].rstrip()

        return head

    def __str__(self):
        return to_utf8(self.text())
    def __unicode__(self):
        return to_unicode(self.text())

    def get_metadata(self):
        """ Return the metadata dict. """
        return self._md

    def _parse(self, elem):
        """
        Parse an update element::

            <!ELEMENT update (id, synopsis?, issued, updated,
                              references, description, rights?,
                              severity?, summary?, solution?, pkglist)>
                <!ATTLIST update type (errata|security) "errata">
                <!ATTLIST update status (final|testing) "final">
                <!ATTLIST update version CDATA #REQUIRED>
                <!ATTLIST update from CDATA #REQUIRED>
        """
        if elem.tag == 'update':
            for attrib in ('from', 'type', 'status', 'version'):
                self._md[attrib] = elem.attrib.get(attrib)
            for child in elem:
                if child.tag == 'id':
                    if not child.text:
                        raise UpdateNoticeException("No id element found")
                    self._md['update_id'] = child.text
                elif child.tag == 'pushcount':
                    self._md['pushcount'] = child.text
                elif child.tag == 'issued':
                    self._md['issued'] = child.attrib.get('date')
                elif child.tag == 'updated':
                    self._md['updated'] = child.attrib.get('date')
                elif child.tag == 'references':
                    self._parse_references(child)
                elif child.tag == 'description':
                    self._md['description'] = child.text
                elif child.tag == 'rights':
                    self._md['rights'] = child.text
                elif child.tag == 'severity':
                    self._md[child.tag] = child.text
                elif child.tag == 'summary':
                    self._md['summary'] = child.text
                elif child.tag == 'solution':
                    self._md['solution'] = child.text
                elif child.tag == 'pkglist':
                    self._parse_pkglist(child)
                elif child.tag == 'title':
                    self._md['title'] = child.text
                elif child.tag == 'release':
                    self._md['release'] = child.text
        else:
            raise UpdateNoticeException('No update element found')

    def _parse_references(self, elem):
        """
        Parse the update references::

            <!ELEMENT references (reference*)>
            <!ELEMENT reference>
                <!ATTLIST reference href CDATA #REQUIRED>
                <!ATTLIST reference type (self|other|cve|bugzilla) "self">
                <!ATTLIST reference id CDATA #IMPLIED>
                <!ATTLIST reference title CDATA #IMPLIED>
        """
        for reference in elem:
            if reference.tag == 'reference':
                data = {}
                for refattrib in ('id', 'href', 'type', 'title'):
                    data[refattrib] = reference.attrib.get(refattrib)
                self._md['references'].append(data)
            else:
                raise UpdateNoticeException('No reference element found')

    def _parse_pkglist(self, elem):
        """
        Parse the package list::

            <!ELEMENT pkglist (collection+)>
            <!ELEMENT collection (name?, package+)>
                <!ATTLIST collection short CDATA #IMPLIED>
                <!ATTLIST collection name CDATA #IMPLIED>
            <!ELEMENT name (#PCDATA)>
        """
        for collection in elem:
            data = { 'packages' : [] }
            if 'short' in collection.attrib:
                data['short'] = collection.attrib.get('short')
            for item in collection:
                if item.tag == 'name':
                    data['name'] = item.text
                elif item.tag == 'package':
                    data['packages'].append(self._parse_package(item))
            self._md['pkglist'].append(data)

    def _parse_package(self, elem):
        """
        Parse an individual package::

            <!ELEMENT package (filename, sum, reboot_suggested)>
                <!ATTLIST package name CDATA #REQUIRED>
                <!ATTLIST package version CDATA #REQUIRED>
                <!ATTLIST package release CDATA #REQUIRED>
                <!ATTLIST package arch CDATA #REQUIRED>
                <!ATTLIST package epoch CDATA #REQUIRED>
                <!ATTLIST package src CDATA #REQUIRED>
            <!ELEMENT reboot_suggested (#PCDATA)>
            <!ELEMENT filename (#PCDATA)>
            <!ELEMENT sum (#PCDATA)>
                <!ATTLIST sum type (md5|sha1) "sha1">
        """
        package = {}
        for pkgfield in ('arch', 'epoch', 'name', 'version', 'release', 'src'):
            package[pkgfield] = elem.attrib.get(pkgfield)

        #  Bad epoch and arch data is the most common (missed) screwups.
        # Deal with bad epoch data.
        if not package['epoch'] or package['epoch'][0] not in '0123456789':
            package['epoch'] = None

        for child in elem:
            if child.tag == 'filename':
                package['filename'] = child.text
            elif child.tag == 'sum':
                package['sum'] = (child.attrib.get('type'), child.text)
            elif child.tag == 'reboot_suggested':
                self._md['reboot_suggested'] = True
        return package

    def xml(self):
        """Generate the xml for this update notice object"""
        msg = """
<update from="%s" status="%s" type="%s" version="%s">
  <id>%s</id>
  <title>%s</title>
  <release>%s</release>
  <issued date="%s"/>
  <description>%s</description>\n""" % (to_xml(self._md['from']),
                to_xml(self._md['status']), to_xml(self._md['type']),
                to_xml(self._md['version']), to_xml(self._md['update_id']),
                to_xml(self._md['title']), to_xml(self._md['release']),
                to_xml(self._md['issued'], attrib=True),
                to_xml(self._md['description']))
        if self._md['updated']:
            # include the updated date in the generated xml
            msg += """ <updated date="%s"/>\n""" % (to_xml(self._md['updated'], attrib=True))
        if self._md['summary']:
            msg += """  <summary>%s</summary>\n""" % (to_xml(self._md['summary']))
        if self._md['solution']:
            msg += """  <solution>%s</solution>\n""" % (to_xml(self._md['solution']))
        if self._md['rights']:
            msg += """  <rights>%s</rights>\n""" % (to_xml(self._md['rights']))        
        if self._md['severity']:
            msg += """  <severity>%s</severity>\n""" % (to_xml(self._md['severity']))

        if self._md['references']:
            msg += """  <references>\n"""
            for ref in self._md['references']:
                if ref['title']:
                    msg += """    <reference href="%s" id="%s" title="%s" type="%s"/>\n""" % (
                    to_xml(ref['href'], attrib=True), to_xml(ref['id'], attrib=True),
                    to_xml(ref['title'], attrib=True), to_xml(ref['type'], attrib=True))
                else:
                    msg += """    <reference href="%s" id="%s"  type="%s"/>\n""" % (
                    to_xml(ref['href'], attrib=True), to_xml(ref['id'], attrib=True),
                    to_xml(ref['type'], attrib=True))

            msg += """  </references>\n"""
        
        if self._md['pkglist']:
            msg += """  <pkglist>\n"""
            for coll in self._md['pkglist']:
                msg += """    <collection short="%s">\n      <name>%s</name>\n""" % (
                      to_xml(coll['short'], attrib=True),
                      to_xml(coll['name']))
  
                for pkg in coll['packages']:
                    msg += """      <package arch="%s" name="%s" release="%s" src="%s" version="%s" epoch="%s">
        <filename>%s</filename>
      </package>\n""" % (to_xml(pkg['arch'], attrib=True),
                                to_xml(pkg['name'], attrib=True),
                                to_xml(pkg['release'], attrib=True),
                                to_xml(pkg['src'], attrib=True),
                                to_xml(pkg['version'], attrib=True),
                                to_xml(pkg['epoch'] or '0', attrib=True),
                                to_xml(pkg['filename']))
                msg += """    </collection>\n"""
            msg += """  </pkglist>\n"""
        msg += """</update>\n"""
        return msg

def _rpm_tup_vercmp(tup1, tup2):
    """ Compare two "std." tuples, (n, a, e, v, r). """
    return rpmUtils.miscutils.compareEVR((tup1[2], tup1[3], tup1[4]),
                                         (tup2[2], tup2[3], tup2[4]))
