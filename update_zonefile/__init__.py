#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Copyright (c) 2018 Daniel Triendl <daniel@pew.cc>
Copyright (c) 2024 Antonio J. Delgado

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

from pathlib import Path
from datetime import datetime
import email.utils as eut
import os
import hashlib
import re
import subprocess
import sys
import textwrap
import shutil
from argparse import ArgumentParser
from dataclasses import dataclass

import validators
import dns.zone
import dns.name
import dns.version
from dns.exception import DNSException
import yaml
import requests


REGEX_DOMAIN = '^(127|0)\\.0\\.0\\.(0|1)[\\s\\t]+(?P<domain>([a-z0-9\\-_]+\\.)+[a-z][a-z0-9_-]*)$'
REGEX_NO_COMMENT = '^#.*|^$'
REGEX_NO_COMMENT_IN_LINE = '^([^#]+)'

@dataclass
class Zone:
    """DNS zone"""
    source: str
    target: str
    origin: str
    from_format: str
    to_format: str


class UpdateZonefile():
    """
    Fetch various blocklists and generate a BIND zone from them.
    Configure BIND to return NXDOMAIN for ad and tracking domains to stop clients
    from contacting them.
    """

    def find_command(self, command):
        """Find a command executable"""
        cmd = ['/usr/bin/which', command]
        result = subprocess.run(cmd, capture_output=True, check=False)
        if result.returncode != 0:
            print(f"Error {result.returncode}. Command: '{' '.join(cmd)}'. \
    Output: {result.stdout}. Errors: {result.stderr}")
        return result.stdout.decode().strip()


    def download_list(self, url):
        """Download a list of domains to block"""
        headers = None

        cache = Path(self.config['cache'], hashlib.sha1(url.encode()).hexdigest())

        if cache.is_file():
            last_modified = datetime.utcfromtimestamp(cache.stat().st_mtime)
            headers = {
                'If-modified-since': eut.format_datetime(last_modified),
                'User-Agent': 'Bind adblock zonfile updater v1.0 \
    (https://github.com/Trellmor/bind-adblock)'}

        try:
            r = requests.get(url, headers=headers, timeout=self.config['req_timeout_s'])

            if r.status_code == 200:
                with cache.open('w', encoding='utf8') as f:
                    f.write(r.text)
                if 'last-modified' in r.headers:
                    last_modified = eut.parsedate_to_datetime(
                        r.headers['last-modified']
                    ).timestamp()
                    os.utime(str(cache), times=(last_modified, last_modified))

                return r.text
        except requests.exceptions.RequestException as e:
            print(e)

        if cache.is_file():
            with cache.open('r', encoding='utf8') as f:
                return f.read()
        return False


    def check_domain(self, domain, origin):
        """Check a domain DNS records"""
        if domain == '':
            return False

        if self.config['wildcard_block']:
            domain = '*.' + domain

        try:
            dns.name.from_text(domain, origin)
        except DNSException:
            return False

        if not validators.domain(domain):
            print(f'Ignoring invalid domain {domain}')
            return False

        return True


    def read_list(self, filename):
        """Read a list from a filename"""
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf8') as f:
                return f.read()
        return False


    def parse_lists(self, origin):
        """Parse a list of domains"""
        domains = set()
        origin_name = dns.name.from_text(origin)
        for item in self.config['lists']:
            data = None
            if 'url' in item:
                print(item['url'])
                data = self.download_list(item['url'])
            elif 'file' in item:
                print(item['file'])
                data = self.read_list(item['file'])

            if data:
                lines = data.splitlines()
                print(f"\t{len(lines)} lines")

                c = len(domains)

                for line in data.splitlines():
                    domain = ''

                    if re.match(REGEX_NO_COMMENT, line):
                        continue

                    m = re.search(REGEX_NO_COMMENT_IN_LINE, line)
                    if m:
                        line = m.group(1).strip()

                    if line == '':
                        continue

                    if item.get('format', 'domain') == 'hosts':
                        m = re.match(REGEX_DOMAIN, line)
                        if m:
                            domain = m.group('domain')
                    else:
                        domain = line

                    domain = domain.strip()
                    if self.check_domain(domain, origin_name):
                        domains.add(domain)

                print(f"\t{len(domains) - c} domains")

        print(f"\nTotal\n\t{len(domains)} domains")
        return domains


    def load_zone(self, zonefile, origin, raw):
        """Load a DNS zone"""
        zone_text = ''
        path = Path(zonefile)
        tmp_path = Path(self.config['cache'], 'tempzone')

        if not path.exists():
            with tmp_path.open('w', encoding='utf-8') as f:
                f.write(
                    f"@ 3600 IN SOA @ admin.{origin}. 0 86400 7200 2592000 " +
                    "86400\n@ 3600 IN NS LOCALHOST."
                )

            self.save_zone(tmp_path, zonefile, origin, raw)

            print(textwrap.dedent('''\
                    Zone file "{0}" created.

                    Add BIND options entry:
                    response-policy {{
                        zone "{1}";
                    }};

                    Add BIND zone entry:
                    zone "{1}" {{
                        type master;
                        file "{0}";
                        masterfile-format {2};
                        allow-query {{ none; }};
                    }};
            ''').format(path.resolve(), origin, 'raw' if raw else 'text'))

        if raw:
            self.compile_zone(
                Zone(
                    source=zonefile,
                    target=tmp_path,
                    origin=origin,
                    from_format='raw',
                    to_format='text'
                )
            )
            path = tmp_path

        with path.open('r', encoding='utf-8') as f:
            for line in f:
                zone_text += line
                if "IN NS" in line:
                    break

        return dns.zone.from_text(zone_text, origin)


    def update_serial(self, zone):
        """Update serial for DNS zone"""
        soaset = zone.get_rdataset('@', dns.rdatatype.SOA)
        soa = soaset[0]
        if dns.version.MAJOR < 2:
            soa.serial += 1
        else:
            soaset.add(soa.replace(serial=soa.serial + 1))


    def check_zone(self, origin, zonefile):
        """Check a DNS zone"""
        cmd = [self.find_command('named-checkzone'), origin, str(zonefile)]
        result = subprocess.run(cmd, capture_output=True, check=False)
        if result.returncode != 0:
            print(f"Error {result.returncode}. Command: '{' '.join(cmd)}'. \
    Output: {result.stdout}. Errors: {result.stderr}")
        return result.returncode == 0


    def rndc_reload(self, cmd):
        """Send reload command to rndc"""
        try:
            r = subprocess.check_output(cmd, stderr=subprocess.PIPE)

        except subprocess.CalledProcessError as e:
            print(f"{e.stderr.decode(sys.getfilesystemencoding())}")
            if "multiple" in e.stderr.decode('utf-8'):
                sys.exit(
                    'Please pass --views the list of configured BIND views containing origin zone.'
                )
            if e.returncode != 0:
                sys.exit(f'rndc failed with return code {e.returncode}')

        print(f"{r.decode(sys.getfilesystemencoding())}")

    def reload_zone(self, origin, views):
        """Reload DNS zone"""
        print("Reloading zones....")
        if views:
            for v in views.split(','):
                print (f"  View='{v}', {origin=} ", end='', flush=True)
                self.rndc_reload( [self.find_command('rndc'), 'reload', origin, "IN", v] )
        else:
            print ("{origin} ", end='', flush=True)
            self.rndc_reload( [self.find_command('rndc'), 'reload', origin] )

    def is_exe(self, fpath):
        """Check if a file is an executable"""
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


    def compile_zone(self, zone):
        """Compile DNS zone"""
        cmd = [
            self.find_command('named-compilezone'),
            '-f',
            zone.from_format,
            '-F',
            zone.to_format,
            '-o',
            str(zone.target),
            zone.origin,
            str(zone.source)]
        r = subprocess.call(cmd)
        if r != 0:
            sys.stderr.write(
                f'named-compilezone {zone} failed with return code {r}.\n'
            )


    def save_zone(self, tmpzonefile, zonefile, origin, raw):
        """Save a DNS zone"""
        if raw:
            self.compile_zone(
                Zone(
                    source=tmpzonefile,
                    target=zonefile,
                    origin=origin,
                    from_format='text',
                    to_format='raw'
                )
            )
        else:
            shutil.move(str(tmpzonefile), str(zonefile))


    def append_domain_to_zonefile(self, file, domain):
        """Append a domain to a zone file"""
        if self.config['blocking_mode'] == 'NXDOMAIN' or "_" in domain:
            file.write(domain + ' IN CNAME .\n')
        else:
            file.write(domain + ' IN A 0.0.0.0\n')
            file.write(domain + ' IN AAAA ::\n')


    def parse_arguments(self):
        """Parse command line arguments"""
        parser = ArgumentParser(description='Update zone file from public DNS ad blocking lists')
        parser.add_argument(
            '--no-bind',
            dest='no_bind',
            action='store_true',
            help='Don\'t try to check/reload bind zone'
        )
        parser.add_argument(
            '--raw',
            dest='raw_zone',
            action='store_true',
            help='Save the zone file in raw format. Requires named-compilezone'
        )
        parser.add_argument(
            '--empty',
            dest='empty',
            action='store_true',
            help='Create header-only (empty) rpz zone file'
        )
        parser.add_argument('--views', dest='views', type=str,
                            help='If using multiple BIND views, list where each zone is defined')
        parser.add_argument('zonefile', help='path to zone file')
        parser.add_argument('origin', help='zone origin')
        args = parser.parse_args()
        return args

    def close(self):
        """Close the class"""

    def _read_config(self):
        self.config = {
            # Blocklist download request timeout
            'req_timeout_s': 10,
            # Also block *.domain.tld
            'wildcard_block': False,
            # Cache directory
            'cache': Path(os.path.dirname(os.path.realpath(__file__)), )
        }

        main_conf_file = os.path.join(
            os.environ['HOME'],
            '.config',
            'update_zonefile.yml'
        )
        if not os.path.exists(main_conf_file):
            prev_conf_file = main_conf_file
            parent_dir = os.path.dirname(os.path.realpath(__file__))
            main_conf_file = os.path.join(parent_dir, 'config.yml')
            if not os.path.exists(main_conf_file):
                sys.stderr.write(
                    f"Configuration file not found in '{prev_conf_file}' or '{main_conf_file}'.\n"
                )
                sys.exit(1)
        with open(main_conf_file, encoding='utf-8') as conf_file:
            self.config = yaml.safe_load(conf_file)
        self.config['cache'] = Path(self.config['cache'])
        if not self.config['cache'].is_absolute():
            self.config['cache'] = Path(parent_dir, self.config['cache'])

    def _check_selinux(self):
        if self.is_exe('/usr/sbin/getenforce'):
            cmd = [self.find_command('getenforce')]
            result = subprocess.check_output(cmd).strip()
            print('SELinux getenforce output / Current State is: ', result)
            if result == b'Enforcing':
                print(
                    'SELinux restorecon being run to reset MAC security context on ' +
                    'zone file'
                )
                if self.is_exe('/sbin/restorecon'):
                    cmd = ['/sbin/restorecon', '-F', self.args.zonefile]
                    result = subprocess.call(cmd)
                    if result != 0:
                        sys.stderr.write(
                            'Cannot run selinux restorecon on the zonefile - ' +
                            f'return code {result}.\n'
                        )
                        sys.exit(2)

    def __init__(self):
        self.config = {}
        self._read_config()
        self.args = self.parse_arguments()

        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        if not self.config['cache'].is_dir():
            self.config['cache'].mkdir(parents=True)

        zone = self.load_zone(self.args.zonefile, self.args.origin, self.args.raw_zone)
        self.update_serial(zone)

        if self.args.empty:
            domains = set()
        else:
            domains = self.parse_lists(self.args.origin)

        tmpzonefile = Path(self.config['cache'], 'tempzone')
        zone.to_file(str(tmpzonefile))

        with tmpzonefile.open('a', encoding='utf-8') as f:
            for d in (sorted(domains)):
                if d in self.config['domain_whitelist']:
                    continue
                self.append_domain_to_zonefile(f, d)
                if self.config['wildcard_block']:
                    self.append_domain_to_zonefile(f, '*.' + d)

        if self.args.no_bind:
            self.save_zone(tmpzonefile, self.args.zonefile, self.args.origin, self.args.raw_zone)
        else:
            if self.check_zone(self.args.origin, tmpzonefile):
                self.save_zone(
                    tmpzonefile,
                    self.args.zonefile,
                    self.args.origin,
                    self.args.raw_zone
                )
                self._check_selinux()
                self.reload_zone(self.args.origin, self.args.views)
            else:
                print('Zone file invalid, not loading')

def __main__(**kwargs):
    obj = UpdateZonefile(**kwargs)
    obj.close()

if __name__ == "__main__":
    __main__()
