from ethel.runners.sbuild import sbuild
from ethel.utils import upload


def run(dsc, package, job):
    suite = job['suite']
    arch = job['arch']
    ftbfs, out, info = sbuild(dsc, suite, arch)
    print(ftbfs, info)
    # fluxbox_1.3.5-1_amd64.changes
    changes = "{package}_{version}_{arch}.changes"
    upload(changes, job)
