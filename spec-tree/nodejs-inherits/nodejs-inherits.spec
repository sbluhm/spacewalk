%{?nodejs_find_provides_and_requires}

Name:           nodejs-inherits
Version:        2.0.3
Release:        7%{?dist}
Summary:        A tiny simple way to do classic inheritance in js
License:        WTFPL
URL:            https://github.com/isaacs/inherits
Source0:        https://registry.npmjs.org/inherits/-/inherits-%{version}.tgz
Source1:        https://raw.github.com/isaacs/inherits/112807f2670160b6e3bafdf39e395c10ae7d0fac/LICENSE
BuildArch:      noarch
ExclusiveArch:  %{nodejs_arches} noarch

BuildRequires:  nodejs-packaging

%description
%{summary}.


%prep
%setup -q -n package
cp -p %{SOURCE1} LICENSE


%build
#nothing to do


%install
mkdir -p %{buildroot}%{nodejs_sitelib}/inherits@2
cp -pr inherits.js package.json %{buildroot}%{nodejs_sitelib}/inherits@2
ln -sf inherits@2 %{buildroot}%{nodejs_sitelib}/inherits
%nodejs_symlink_deps


%check
%nodejs_symlink_deps --check

# Upstream no longer includes test.js with its tarballs
# %__nodejs test.js


# there have been reports that the symlinks are messed up when upgrading
# from older versions, so let's make sure everything's copacetic
%triggerun -- nodejs-inherits < 2.0.0-4
ln -sf inherits@2 %{nodejs_sitelib}/inherits
%{__python3} <<EOF
import json, os, sys

for moddir in os.listdir('%{nodejs_sitelib}'):
    if os.path.isdir(moddir):
        md = json.load(open(os.path.join(moddir, 'package.json')))
        
        if 'dependencies' in md and 'inherits' in md['dependencies']:
            if isinstance(md['dependencies'], dict) and '1' in md['dependencies']['inherits']:
                src = os.path.join('%{nodejs_sitelib}', 'inherits@1')
            else:
                src = os.path.join('%{nodejs_sitelib}', 'inherits@2')
                
            dest = os.path.join('%{nodejs_sitelib}', moddir, 'node_modules/inherits')
            
            if not os.path.realpath(dest) == src:
                try:
                    os.unlink(dest)
                except OSError:
                    pass
                    
                try:
                    os.symlink(src, dest)
                except OSError, e:
                    sys.stderr.write(e + '\n')
EOF


# rpm blows up if you try to replace a dir with a symlink or vice-versa
%pretrans -p <lua>
if posix.stat("%{nodejs_sitelib}/inherits", "type") == "directory" then
    os.rename('%{nodejs_sitelib}/inherits', '%{nodejs_sitelib}/inherits@2')
end


%files
%doc README.md
%license LICENSE
%{nodejs_sitelib}/inherits@2
%{nodejs_sitelib}/inherits


%changelog
* Sat May 09 2020 Stefan Bluhm <stefan.bluhm@clacee.eu> - 2.0.3-7
- Updated Python macro to Python 3

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue May 30 2017 Stephen Gallagher <sgallagh@redhat.com> - 2.0.3-1
- Update to upstream 2.0.3 release
- Reduces package size and adds a safe import check
- Upstream tests are no longer shipped in the tarball, so they won't be run

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.1-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Tue Jan 26 2016 Tom Hughes <tom@compton.nu> - 2.0.1-7
- Cleanup spec file, removing %%defattr and enabling tests

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sun Oct 26 2014 Tom Hughes <tom@compton.nu> - 2.0.1-5
- update to 2.0.1 upstream release

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri Aug 16 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 2.0.0-4
- add some post-install hackery to work around potential RPM bug resulting in
  symlinks still pointing to their old locations on upgrade (RHBZ#997978)

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Sat Jul 06 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 2.0.0-3
- only run the hack when we really need to

* Sat Jul 06 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 2.0.0-2
- use lua for pretrans

* Sun Jun 23 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 2.0.0-1
- new upstream release 2.0.0
- include license file
- follow the mutiple version spec

* Sun Jun 23 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-9
- restrict to compatible arches

* Mon Apr 15 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-8
- add macro for EPEL6 dependency generation

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Tue Jan 08 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-6
- add missing build section

* Thu Jan 03 2013 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-5
- correct license tag (thanks to Robin Lee)

* Mon Dec 31 2012 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-4
- clean up for submission

* Fri Apr 27 2012 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-3
- guard Requires for F17 automatic depedency generation

* Sat Feb 11 2012 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-2
- switch to automatically generated provides/requires

* Sat Jan 21 2012 T.C. Hollingsworth <tchollingsworth@gmail.com> - 1.0.0-1
- initial package
