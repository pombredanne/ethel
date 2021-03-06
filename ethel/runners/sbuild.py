from ethel.utils import safe_run, run_command, tdir

from firehose.model import Issue, Message, File, Location, Stats, DebianBinary
import firehose.parsers.gcc as fgcc

from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
import sys
import re
import os


STATS = re.compile("Build needed (?P<time>.*), (?P<space>.*) dis(c|k) space")
VERSION = re.compile("sbuild \(Debian sbuild\) (?P<version>)")

def parse_sbuild_log(log, sut):
    gccversion = None
    stats = None

    for line in log.splitlines():
        flag = "Toolchain package versions: "
        stat = STATS.match(line)
        if stat:
            info = stat.groupdict()
            hours, minutes, seconds = [int(x) for x in info['time'].split(":")]
            timed = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            stats = Stats(timed.total_seconds())
        if line.startswith(flag):
            line = line[len(flag):].strip()
            packages = line.split(" ")
            versions = {}
            for package in packages:
                if "_" not in package:
                    continue
                b, bv = package.split("_", 1)
                versions[b] = bv
            vs = list(filter(lambda x: x.startswith("gcc"), versions))
            if vs == []:
                continue
            vs = vs[0]
            gccversion = versions[vs]

    obj = fgcc.parse_file(
        StringIO(log),
        sut=sut,
        gccversion=gccversion,
        stats=stats
    )

    return obj


def sbuild(package, suite, arch):
    chroot = "%s-%s" % (suite, arch)

    dsc = os.path.basename(package)
    if not dsc.endswith('.dsc'):
        raise ValueError("WTF")

    source, dsc = dsc.split("_", 1)
    version, _ = dsc.rsplit(".", 1)
    local = None
    if "-" in version:
        version, local = version.rsplit("-", 1)

    suite, arch = chroot.split("-", 1)
    sut = DebianBinary(source, version, local, arch)

    out, err, ret = run_command([
        "sbuild",
        "-A",
        "-c", chroot,
        "-v",
        "-d", suite,
        "-j", "8",
        package,
    ])
    ftbfs = ret != 0
    info = parse_sbuild_log(out, sut=sut)

    return info, out, ftbfs

# FIXME: do we want to use sbuild version and/or compiler version
# see gcc version in parse_sbuild_log
def version():
    out, err, ret = run_command([
        "sbuild", '--version'
    ])
    # TODO check ret
    vline = out.splitlines()[0]
    v = VERSION.match(vline)
    vdict = v.groupdict()
    return ('sbuild', vdict['version'])
