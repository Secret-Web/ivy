import sys
import stat
import os
from os.path import expanduser
import traceback
import shutil
import asyncio
import subprocess
import logging
from asyncio.subprocess import PIPE, STDOUT
from contextlib import suppress


PATH = os.path.dirname(os.path.realpath(__file__))

SYMLINKS = [
    ('ivy-boot.service', '/etc/systemd/system/ivy-boot.service'),
    ('ivy-<gpu>.service', '/etc/systemd/system/ivy.service')
#    ('i3status.conf', '/etc/i3status.conf'),
#    ('i3config.conf', os.path.expanduser('~/.config/i3/config')),
#    ('Xresources', os.path.expanduser('~/.Xresources'))
#    ('tty1@override.conf', '/etc/systemd/system/getty@tty1.service.d/override.conf')
]

VERSION = {'version': '0.1.0', 'codename': 'Alpha Centauri'}
VERSION['codename_lower'] = VERSION['codename'].lower()

GFX_VERSION = {
    'NVIDIA': '390',
    'AMD': '180.10-572953'
}

#KERNEL_VERSION = '4.15.0'

class LastPartFilter(logging.Filter):
    def filter(self, record):
        record.name_last = record.name.rsplit('.', 1)[-1]
        return True
logger = logging.getLogger('Ivy')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(name_last)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
handler.addFilter(LastPartFilter())

async def system_check():
    try:
        step = new_step('SYSPATCH', 'Checking for new system patches')
        await run_command(step, 'apt', 'update')

        step.info('Applying system patches')
        await run_command(step, 'apt', '-y', '-o', 'Dpkg::Options::="--force-confdef"', '-o', 'Dpkg::Options::="--force-confold"', 'upgrade')
        await run_command(step, 'apt', '-y', 'autoremove')

        step = new_step('BRANDING', 'Applying branding')
        with open('/etc/issue', 'w') as f:
            f.write('Ivy {version} ({codename}) - SecretWeb.com \\l\n'.format(**VERSION))
        with open('/etc/dpkg/origins/default', 'w') as f:
            f.write('''
Vendor: Ivy
Vendor-URL: http://ivy.secretweb.com/
Bugs: https://forum.secretweb.com/
Parent: Ubuntu
''')
        with open('/etc/lsb-release', 'w') as f:
            f.write('''
DISTRIB_ID=Ivy
DISTRIB_RELEASE={version}
DISTRIB_CODENAME="{codename}"
DISTRIB_DESCRIPTION="Ivy 0.1.0"
'''.format(**VERSION))
        with open('/etc/os-release', 'w') as f:
            f.write('''
NAME="Ivy"
VERSION="{version} ({codename})"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ivy {version} ({codename})"
VERSION_ID="0.1.0"
HOME_URL="http://ivy.secretweb.com/"
SUPPORT_URL="http://help.secretweb.com/"
BUG_REPORT_URL="http://forum.secretweb.com/"
VERSION_CODENAME="{codename_lower}"
UBUNTU_CODENAME=xenial
'''.format(**VERSION))
        with open('/etc/profile.d/00-aliases.sh', 'w') as f:
            f.write('alias screenfetch=/bin/bash /opt/ivy/system/fetch.sh')

        #logger.info('STEP: Updating Kernel')
        #await run_command(step, 'apt', 'install', '-y', 'linux-image-' + KERNEL_VERSION, 'linux-headers-' + KERNEL_VERSION, 'linux-image-extra-' + KERNEL_VERSION)

        step = new_step('TOOLS', 'Installing tools')
        await run_command(step, 'apt', 'install', '-y', 'libcurl4-openssl-dev', 'libssl-dev', 'libjansson-dev', 'automake', 'autotools-dev', 'build-essential')
        await run_command(step, 'apt', 'install', '-y', 'gcc-5', 'g++-5')
        await run_command(step, 'update-alternatives', '--install', '/usr/bin/gcc', 'gcc', '/usr/bin/gcc-5', '1')
        await run_command(step, 'apt', 'install', '-y', 'software-properties-common')
        await run_command(step, 'apt', 'install', '-y', 'lshw', 'ocl-icd-opencl-dev', 'libcurl4-openssl-dev')

        step = new_step('XORG', 'Installing XOrg + i3')
        await run_command(step, 'apt', 'install', '-y', 'xorg', 'i3', 'jq', 'chromium-browser')
        await run_command(step, 'systemctl', 'set-default', 'multi-user.target')
        await run_command(step, 'usermod', '-a', '-G', 'video', 'ivy')
        await run_command(step, 'apt', 'install', '-y', 'xvfb')

        step = new_step('CLEANING', 'Removing unnecessary packages')
        await run_command(step, 'apt', 'autoremove', '-y')

        step = new_step('PYTHON', 'Installing python requirements')
        await run_command(step, sys.executable, '-m', 'pip', 'install', '-r', os.path.join(PATH, '../requirements.txt'))

        step = new_step('GRAPHICS', 'Detecting graphics cards')

        await run_command(step, 'update-pciids')

        p = subprocess.Popen('lspci -vnnn | grep VGA', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.communicate()[0].decode('UTF-8').strip()
        graphics = ['Intel' if 'Intel' in line else 'AMD' if 'AMD' in line else 'NVIDIA' if 'NVIDIA' in line else 'Unknown' for line in out.split('\n')]

        step.info('Cards: %r' % graphics)

        await asyncio.sleep(1)

        step = new_step('SYMLINKS', 'Creating symlinks')
        for f, t in SYMLINKS:
            if '<gpu>' in f:
                f = f.replace('<gpu>', 'nvidia' if 'NVIDIA' in graphics else 'other')
            t = os.path.abspath(t)

            with suppress(FileNotFoundError):
                os.remove(t)

            step.info(os.path.join(PATH, f) + ' -> ' + t)
            os.link(os.path.join(PATH, f), t)
        await run_command(step, 'systemctl', 'daemon-reload')

        step = new_step('DRIVERS', 'Verifying graphics drivers')

        installed = False

        if 'NVIDIA' in graphics:
            step = new_step('NVIDIA', 'Verifying NVIDIA drivers')

            await asyncio.sleep(1)

            if not is_installed('nvidia-390'):
                step.info('Installing NVIDIA drivers')
                await run_command(step, 'add-apt-repository', '-y', 'ppa:graphics-drivers')
                await run_command(step, 'apt', 'update')
                await run_command(step, 'apt', 'install', '-y', 'nvidia-%s' % GFX_VERSION['NVIDIA'], 'nvidia-cuda-toolkit')

                installed = True

        if 'AMD' in graphics:
            step = new_step('AMD', 'Verifying AMD drivers')

            await asyncio.sleep(1)

            if not is_installed('amdgpu-pro-core') and not is_installed('amdgpu-pro') and not is_installed('amdgpu'):
                step.info('Installing AMD drivers')

                await run_command(step, 'apt', 'install', '-y', 'amdgpu-dkms', 'libdrm-amdgpu-amdgpu1', 'libdrm-amdgpu1', 'libdrm2-amdgpu')

                await run_command(step, 'wget', '--referer=http://support.amd.com', '--limit-rate', '1024k', 'https://www2.ati.com/drivers/linux/ubuntu/amdgpu-pro-18.10-572953.tar.xz', '-O', 'amdgpu-pro.tar.gz', cwd='/tmp')

                TMP_DIR = '/tmp/amdgpu-pro'
                with suppress(FileNotFoundError):
                    shutil.rmtree(TMP_DIR)
                os.mkdir(TMP_DIR)
                await run_command(step, 'tar', 'xvfJ', 'amdgpu-pro.tar.gz', '-C', TMP_DIR, cwd='/tmp')
                await run_command(step, './amdgpu-install', '-y', '--opencl=legacy', '--headless', cwd=os.path.join(TMP_DIR, os.listdir(TMP_DIR)[0]))

                '''await run_command(step, 'add-apt-repository', 'ppa:paulo-miguel-dias/mesa')
                await run_command(step, 'apt', 'update')
                await run_command(step, 'apt', 'install', '-y', 'libclc-amdgcn', 'mesa-opencl-icd')

                logger.info('STEP: Installing HWE Kernel')

                await run_command(step, 'apt', 'install', '--install-recommends', 'linux-generic-hwe-16.04', 'xserver-xorg-hwe-16.04')

                '''
                installed = True

            # For AMD table overriding
            step = new_step('OHGODATOOL', 'Installing OhGodATool')

            await asyncio.sleep(1)

            await run_command(step, 'apt', 'install', '-y', 'libpci-dev')

            OHGODATOOL_PATH = os.path.join('/opt', 'OhGodATool/')
            if not os.path.exists(OHGODATOOL_PATH):
                await run_command(step, 'git', 'clone', 'https://github.com/OhGodACompany/OhGodATool.git', cwd='/opt')

            await run_command(step, 'git', 'pull', cwd=OHGODATOOL_PATH)

            # TODO: Only run this if there was an update
            await run_command(step, 'make', cwd=OHGODATOOL_PATH)

            OHGODATOOL_USR_BIN = os.path.join('/usr', 'bin', 'ohgodatool')
            with suppress(FileNotFoundError):
                os.remove(OHGODATOOL_USR_BIN)
            os.link(os.path.join(OHGODATOOL_PATH, 'ohgodatool'), OHGODATOOL_USR_BIN)

        if installed:
            await run_command(step, 'shutdown', '-r', 'now')

        await asyncio.sleep(5)

        await run_command(step, 'systemctl', 'enable', 'ivy')
        await run_command(step, 'service', 'ivy', 'start')
    except Exception as e:
        logger.info('- Error -')
        logger.info(traceback.format_exc())

        await asyncio.sleep(10)

    loop.stop()

def is_installed(pkg):
    p = subprocess.Popen(['dpkg', '-l', pkg], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = [x.decode('UTF-8', errors='ignore').strip() for x in p.communicate()]
    logger.info(out if out else err)
    return 'no packages' not in err

def new_step(tag, name):
    logger.info(name)
    return logger.getChild(tag)


async def run_command(logger, *args, cwd=None):
    if cwd is None:
        cwd = os.path.dirname(os.path.realpath(__file__))

    logger.info(' '.join(args))

    process = await asyncio.subprocess.create_subprocess_exec(*args, \
                                    cwd=cwd, \
                                    stdin=PIPE, stdout=PIPE, stderr=PIPE)

    asyncio.ensure_future(_read_stream(logger, process.stdout, is_error=False))
    asyncio.ensure_future(_read_stream(logger, process.stderr, is_error=True))

    return await process.wait()

async def _read_stream(logger, stream, is_error):
    while True:
        output = await stream.readline()
        if not output: break

        output = output.decode('UTF-8', errors='ignore').replace('\n', '').strip()
        if len(output) == 0: continue

        logger.info(output)

logger.info('----------< Ivy {version} ({codename}) >----------'.format(**VERSION))
logger.info('')
logger.info('')
logger.info('')

loop = asyncio.get_event_loop()

loop.run_until_complete(system_check())

