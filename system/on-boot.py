import sys
import os
from os.path import expanduser
import shutil
import asyncio
import subprocess
from asyncio.subprocess import PIPE, STDOUT
from contextlib import suppress

import urwid


HOME = expanduser('~')
PATH = os.path.dirname(os.path.realpath(__file__))

SYMLINKS = [
    ('i3status.conf', '/etc/i3status.conf'),
    ('i3config.conf', '~/.config/i3/config'),
    ('Xresources', '~/.Xresources'),
    ('tty1@override.conf', '/etc/systemd/system/getty@tty1.service.d/override.conf')
]

GFX_VERSION = {
    'NVIDIA': '390',
    'AMD': '180.10-572953'
}

palette = [
    ('header', '', '', '', '#FFF,bold', '#558'),
    ('footer', '', '', '', '#FFF,italics', '#558'),

    ('background', '', '', '', '#FFF', '#000'),

    ('log', '', '', '', '#888', '#000'),

    ('progress-normal', '', '', '', '#FFF', '#55C'),
    ('progress-complete', '', '', '', '#000', '#FFF'),
    ('progress-smooth', '', '', '', '#CCC', '#888')
]

class Display:
    def __init__(self, loop):
        self.step_i = 0
        self.steps_max = 0
        with open(__file__, 'r') as f:
            self.steps_max = f.read().count('step_done(') - 2

        self.operation = urwid.Text('', align='center')

        self.step_text = urwid.Text('', align='center')

        self.progress = urwid.ProgressBar('progress-normal', 'progress-complete', 0, 1, 'progress-smooth')

        self.branding = urwid.Text('- SecretWeb.com -', align='center')

        self.output_lines = urwid.SimpleListWalker([])
        self.output = urwid.ListBox(self.output_lines)

        self.urwid = urwid.MainLoop(
            urwid.AttrMap(urwid.Filler(
                urwid.Pile([
                    urwid.AttrMap(urwid.Pile([urwid.Divider(), urwid.Text('Ivy', align='center'), urwid.Divider()]), 'header'),

                    urwid.Divider(),

                    urwid.Padding(urwid.Pile([
                        self.operation,

                        self.step_text,

                        urwid.Divider(),

                        self.progress,

                        urwid.Divider(),
                        urwid.Divider(),

                        urwid.AttrMap(urwid.BoxAdapter(self.output, height=16), 'log'),

                        urwid.Divider(),
                        urwid.Divider()
                    ]), left=2, right=2),

                    urwid.AttrMap(self.branding, 'footer')
                ])
            ), 'background'),
            palette,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

        self.urwid.screen.set_terminal_properties(colors=256)

    def add_line(self, output):
        self.output_lines.append(urwid.Text(output))
        self.output_lines.set_focus(len(self.output_lines) - 1)

    def set_step(self, text):
        self.operation.set_text(text)
        self.add_line('%s...' % self.operation.text)

    def step_done(self):
        self.step_i += 1

        self.step_text.set_text('%d / %d' % (self.step_i, self.steps_max))
        self.progress.set_completion(self.step_i / self.steps_max)

    def run(self):
        self.urwid.run()

async def system_check():
    display.set_step('Applying branding')
    with open('/etc/issue', 'w') as f:
        f.write('Ivy - SecretWeb.com \\l\n')
    display.step_done()

    display.set_step('Cleaning symlinks')
    for f, t in SYMLINKS:
        os.makedirs(os.path.dirname(os.path.realpath(t)), exist_ok=True)
        with suppress(FileNotFoundError):
            os.remove(os.path.realpath(t))
    display.step_done()

    display.set_step('Checking for system patches')
    await run_command('apt', 'update')
    await run_command('apt', 'upgrade', '-y')
    await run_command('apt', 'autoremove', '-y')
    display.step_done()

    display.set_step('Installing tools')
    await run_command('apt', 'install', '-y', 'libcurl4-openssl-dev', 'libssl-dev', 'libjansson-dev', 'automake', 'autotools-dev', 'build-essential')
    await run_command('apt', 'install', '-y', 'gcc-5', 'g++-5')
    await run_command('update-alternatives', '--install', '/usr/bin/gcc', 'gcc', '/usr/bin/gcc-5', '1')
    await run_command('apt', 'install', '-y', 'software-properties-common')
    await run_command('apt', 'install', '-y', 'lshw', 'ocl-icd-opencl-dev', 'libcurl4-openssl-dev')
    display.step_done()

    display.set_step('Installing XOrg + i3')
    await run_command('apt', 'install', '-y', 'xorg', 'i3', 'jq', 'chromium-browser')
    await run_command('systemctl', 'set-default', 'multi-user.target')
    await run_command('usermod', '-a', '-G', 'video', 'ivy')
    display.step_done()

    display.set_step('Installing python requirements')
    await run_command(sys.executable, '-m', 'pip', 'install', '-r', os.path.join(PATH, '../requirements.txt'))
    display.step_done()

    display.set_step('Creating symlinks')
    for f, t in SYMLINKS:
        os.link(os.path.join(PATH, f), os.path.realpath(t))
    await run_command('systemctl', 'daemon-reload')
    display.step_done()

    display.set_step('Verifying graphics drivers')

    p = subprocess.Popen('lspci -vnnn | grep VGA', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.communicate()[0].decode('UTF-8').strip()
    graphics = ['Intel' if 'Intel' in line else 'AMD' if 'AMD' in line else 'NVIDIA' if 'NVIDIA' in line else 'Unknown' for line in out.split('\n')]

    display.add_line('Cards: %r' % graphics)

    await asyncio.sleep(1)

    installed = False

    if 'NVIDIA' in graphics:
        display.set_step('Verifying NVIDIA drivers')

        await asyncio.sleep(1)

        if not is_installed('nvidia-390'):
            display.set_step('Installing NVIDIA drivers')
            await run_command('add-apt-repository', '-y', 'ppa:graphics-drivers')
            await run_command('apt', 'update')
            await run_command('apt', 'install', '-y', 'nvidia-%s' % GFX_VERSION['NVIDIA'], 'nvidia-cuda-toolkit')

            installed = True

    if 'AMD' in graphics:
        display.set_step('Verifying AMD drivers')

        await asyncio.sleep(1)

        if not is_installed('amdgpu-pro') and not is_installed('amdgpu'):
            display.set_step('Installing AMD drivers')

            #await run_command('apt', 'install', '-y', 'amdgpu-pros')

            await run_command('wget', '--referer=http://support.amd.com', 'https://www2.ati.com/drivers/linux/ubuntu/amdgpu-pro-18.10-572953.tar.xz', '-O', 'amdgpu-pro.tar.gz', cwd='/tmp')

            TMP_DIR = '/tmp/amdgpu-pro'
            with suppress(FileNotFoundError):
                shutil.rmtree(TMP_DIR)
            os.mkdir(TMP_DIR)
            await run_command('tar', 'xvfJ', 'amdgpu-pro.tar.gz', '-C', TMP_DIR, cwd='/tmp')
            await run_command('./amdgpu-install', '-y', '--opencl=rocm', cwd=os.path.join(TMP_DIR, os.listdir(TMP_DIR)[0]))

            await run_command('add-apt-repository', 'ppa:paulo-miguel-dias/mesa')
            await run_command('apt', 'update')
            await run_command('apt', 'install', '-y', 'libclc-amdgcn', 'mesa-opencl-icd')

            installed = True

        display.set_step('Installing OhGodATool')

        await asyncio.sleep(1)

        await run_command('apt', 'install', '-y', 'libpci-dev')

        OHGODATOOL_PATH = os.path.join('/opt', 'OhGodATool/')
        if not os.path.exists(OHGODATOOL_PATH):
            await run_command('git', 'clone', 'https://github.com/OhGodACompany/OhGodATool.git', cwd='/opt')

        await run_command('git', 'pull', cwd=OHGODATOOL_PATH)

        # TODO: Only run this if there was an update
        await run_command('make', cwd=OHGODATOOL_PATH)

        OHGODATOOL_USR_BIN = os.path.join('/usr', 'bin', 'ohgodatool')
        with suppress(FileNotFoundError):
            os.remove(OHGODATOOL_USR_BIN)
        os.link(os.path.join(OHGODATOOL_PATH, 'ohgodatool'), OHGODATOOL_USR_BIN)

    if installed:
        await run_command('shutdown', '-r', 'now')

    display.step_done()

    await asyncio.sleep(5)

    loop.stop()

def is_installed(pkg):
    p = subprocess.Popen(['dpkg', '-l', pkg], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = [x.decode('UTF-8', errors='ignore').strip() for x in p.communicate()]
    display.add_line(out if out else err)
    return 'no packages' not in err

async def run_command(*args, cwd=None):
    if cwd is None:
        cwd = os.path.dirname(os.path.realpath(__file__))

    display.add_line(' '.join(args))

    process = await asyncio.subprocess.create_subprocess_exec(*args, \
                                    cwd=cwd, \
                                    stdin=PIPE, stdout=PIPE, stderr=PIPE)

    asyncio.ensure_future(_read_stream(process.stdout, is_error=False))
    asyncio.ensure_future(_read_stream(process.stderr, is_error=True))

    return await process.wait()

async def _read_stream(stream, is_error):
    while True:
        output = await stream.readline()
        if not output: break

        output = output.decode('UTF-8', errors='ignore').replace('\n', '')
        display.add_line(output)

loop = asyncio.get_event_loop()

display = Display(loop=loop)

loop.create_task(system_check())

display.run()
