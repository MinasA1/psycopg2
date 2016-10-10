#!/usr/bin/env python
"""Generate the errorcodes module starting from PostgreSQL documentation.

The script can be run at a new PostgreSQL release to refresh the module.
"""

# Copyright (C) 2010 Daniele Varrazzo  <daniele.varrazzo@gmail.com>
#
# psycopg2 is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# psycopg2 is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
# License for more details.

import re
import sys
import urllib2
from collections import defaultdict

from BeautifulSoup import BeautifulSoup as BS


def main():
    if len(sys.argv) != 2:
        print >>sys.stderr, "usage: %s /path/to/errorcodes.py" % sys.argv[0]
        return 2

    filename = sys.argv[1]

    file_start = read_base_file(filename)
    # If you add a version to the list fix the docs (errorcodes.rst, err.rst)
    classes, errors = fetch_errors(
        ['8.1', '8.2', '8.3', '8.4', '9.0', '9.1', '9.2', '9.3', '9.4', '9.5'])

    f = open(filename, "w")
    for line in file_start:
        print >>f, line
    for line in generate_module_data(classes, errors):
        print >>f, line


def read_base_file(filename):
    rv = []
    for line in open(filename):
        rv.append(line.rstrip("\n"))
        if line.startswith("# autogenerated"):
            return rv

    raise ValueError("can't find the separator. Is this the right file?")


def parse_errors_txt(url):
    classes = {}
    errors = defaultdict(dict)

    page = urllib2.urlopen(url)
    for line in page:
        # Strip comments and skip blanks
        line = line.split('#')[0].strip()
        if not line:
            continue

        # Parse a section
        m = re.match(r"Section: (Class (..) - .+)", line)
        if m:
            label, class_ = m.groups()
            classes[class_] = label
            continue

        # Parse an error
        m = re.match(r"(.....)\s+(?:E|W|S)\s+ERRCODE_(\S+)(?:\s+(\S+))?$", line)
        if m:
            errcode, macro, spec = m.groups()
            # skip errcodes without specs as they are not publically visible
            if not spec:
                continue
            errlabel = spec.upper()
            errors[class_][errcode] = errlabel
            continue

        # We don't expect anything else
        raise ValueError("unexpected line:\n%s" % line)

    return classes, errors


def parse_errors_sgml(url):
    page = BS(urllib2.urlopen(url))
    table = page('table')[1]('tbody')[0]

    classes = {}
    errors = defaultdict(dict)

    for tr in table('tr'):
        if tr.td.get('colspan'):    # it's a class
            label = ' '.join(' '.join(tr(text=True)).split()) \
                .replace(u'\u2014', '-').encode('ascii')
            assert label.startswith('Class')
            class_ = label.split()[1]
            assert len(class_) == 2
            classes[class_] = label

        else:   # it's an error
            errcode = tr.tt.string.encode("ascii")
            assert len(errcode) == 5

            tds = tr('td')
            if len(tds) == 3:
                errlabel = '_'.join(tds[1].string.split()).encode('ascii')

                # double check the columns are equal
                cond_name = tds[2].string.strip().upper().encode("ascii")
                assert errlabel == cond_name, tr

            elif len(tds) == 2:
                # found in PG 9.1 docs
                errlabel = tds[1].tt.string.upper().encode("ascii")

            else:
                assert False, tr

            errors[class_][errcode] = errlabel

    return classes, errors

errors_sgml_url = \
    "http://www.postgresql.org/docs/%s/static/errcodes-appendix.html"

errors_txt_url = \
    "http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob_plain;" \
    "f=src/backend/utils/errcodes.txt;hb=REL%s_STABLE"


def fetch_errors(versions):
    classes = {}
    errors = defaultdict(dict)

    for version in versions:
        print >> sys.stderr, version
        tver = tuple(map(int, version.split('.')))
        if tver < (9, 1):
            c1, e1 = parse_errors_sgml(errors_sgml_url % version)
        else:
            c1, e1 = parse_errors_txt(
                errors_txt_url % version.replace('.', '_'))
        classes.update(c1)
        for c, cerrs in e1.iteritems():
            errors[c].update(cerrs)

    return classes, errors


def generate_module_data(classes, errors):
    yield ""
    yield "# Error classes"
    for clscode, clslabel in sorted(classes.items()):
        err = clslabel.split(" - ")[1].split("(")[0] \
            .strip().replace(" ", "_").replace('/', "_").upper()
        yield "CLASS_%s = %r" % (err, clscode)

    for clscode, clslabel in sorted(classes.items()):
        yield ""
        yield "# %s" % clslabel

        for errcode, errlabel in sorted(errors[clscode].items()):
            yield "%s = %r" % (errlabel, errcode)


if __name__ == '__main__':
    sys.exit(main())
