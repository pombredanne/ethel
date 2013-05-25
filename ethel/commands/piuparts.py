from ethel.chroot import schroot, copy, scmd, get_tarball
from ethel.utils import EthelSubprocessError

from firehose.model import Issue, Message, File, Location
from storz.wrapper import generate_analysis

import sys
import os
import re


LINE_INFO = re.compile(
    r"(?P<minutes>\d+)m(?P<sec>(\d(\.?))+)s (?P<severity>\w+): (?P<info>.*)")


def piuparts(chroot, package):
    analysis = generate_analysis("piuparts", "unstable", package)
    tarball = get_tarball(chroot)

    name = os.path.basename(tarball)
    internal_path = "/tmp/%s" % (name)

    package_name = os.path.basename(package)
    internal_package = "/tmp/%s" % (package_name)

    with schroot(chroot) as session:

        copy(session, tarball, internal_path)
        copy(session, package, internal_package)

        print("Installing...")
        scmd(session, [
            'apt-get', 'install', '-y', 'piuparts'
        ], user='root')

        print("Piuparts installed.")

        failed = False
        try:
            print("Running Piuparts..")
            out, err = scmd(session, [
                'piuparts',
                    '-b', internal_path,
                    internal_package,
                    '--warn-on-debsums-errors',
                    '--pedantic-purge-test',
            ], user='root')
        except EthelSubprocessError as e:
            out, err = e.out, e.err
            failed = True

        for x in parse_log(out.splitlines(), package):
            analysis.results.append(x)

        return failed, out, analysis


def parse_log(lines, path):
    obj = None
    info = None
    cur_msg = ""

    cat = {
        "dependency-is-messed-up": [
            "E: Unable to correct problems, you have held broken packages.",
        ],
        "conffile-stuff-sucks": ["owned by: .+"],
        "command-not-found": ["command not found|: not found"],
        "conffile-modified": [
            "debsums reports modifications inside the chroot"
        ]
    }

    def handle_obj(obj):
        obj.message = Message(text=cur_msg)
        for k, v in cat.items():
            for expr in v:
                if re.findall(expr, cur_msg) != []:
                    obj.testid = k
                    break
        #if obj.testid is None:
        #    print(cur_msg)
        #    raise Exception
        return obj

    for line in lines:
        if line.startswith(" "):
            cur_msg += "\n" + line.strip()
            continue

        match = LINE_INFO.match(line)
        if match is None:
            continue

        info = match.groupdict()
        if info['severity'] in ['DEBUG', 'DUMP', 'INFO']:
            continue

        if obj:
            yield handle_obj(obj)
            cur_msg = ""

        obj = Issue(cwe=None,
                    testid=None,
                    location=Location(file=File(path, None),
                                      function=None,
                                      point=None),
                    severity=info['severity'],
                    message=Message(text=""),
                    notes=None,
                    trace=None)
    if obj:
        yield handle_obj(obj)


def main():
    output = open(sys.argv[3], 'wb')
    report = piuparts(*sys.argv[1:2])
    output.write(report.to_xml_bytes())