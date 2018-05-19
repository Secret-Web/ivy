import sys
import os
from os.path import expanduser
import re
import asyncio
import subprocess
from asyncio.subprocess import PIPE, STDOUT
from contextlib import suppress

import urwid


HOME = expanduser('~')
PATH = os.path.dirname(os.path.realpath(__file__))

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

def is_installed(pkg):
    p = subprocess.Popen(['dpkg', '-l', pkg], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = [x.decode('UTF-8', errors='ignore').strip() for x in p.communicate()]
    display.add_line(out if out else err)
    return 'no packages' not in err

async def system_check():
    display.set_step('Applying branding')
    with open('/etc/issue', 'w') as f:
        f.write('Ivy - SecretWeb.com \\l\n')
    display.step_done()

    display.set_step('Checking for system patches')
    await run_command('apt', 'update')
    await run_command('apt', 'upgrade', '-y')
    await run_command('apt', 'autoremove', '-y')
    display.step_done()

    display.set_step('Installing tools')
    await run_command('apt', 'install', '-y', *'libcurl4-openssl-dev libssl-dev libjansson-dev automake autotools-dev build-essential'.split(' '))
    await run_command('apt', 'install', '-y', 'gcc-5', 'g++-5')
    await run_command('update-alternatives', '--install', '/usr/bin/gcc', 'gcc', '/usr/bin/gcc-5', '1')
    await run_command('apt', 'install', '-y', 'software-properties-common')
    await run_command('apt', 'install', '-y', *'lshw ocl-icd-opencl-dev libcurl4-openssl-dev'.split(' '))
    display.step_done()

    display.set_step('Installing XOrg + i3')
    await run_command('apt', 'install', '-y', 'xorg', 'i3', 'jq', 'chromium-browser')
    await run_command('systemctl', 'set-default', 'multi-user.target')
    await run_command('usermod', '-a', '-G', 'video', 'ivy')
    display.step_done()

    display.set_step('Installing python requirements')
    await run_command(sys.executable, '-m', 'pip', 'install', '-r', os.path.join(PATH, '../requirements.txt'))
    display.step_done()

    display.set_step('Verifying graphics drivers')

    p = subprocess.Popen('lspci -vnnn | grep VGA', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.communicate()[0].decode('UTF-8').strip()
    graphics = ['Intel' if 'Intel' in line else 'AMD' if 'AMD' in line else 'NVIDIA' if 'NVIDIA' in line else 'Unknown' for line in out.split('\n')]

    display.add_line('Cards: %r' % graphics)

    installed = False

    if 'NVIDIA' in graphics:
        display.set_step('Verifying NVIDIA drivers')
        if not is_installed('nvidia-390'):
            display.set_step('Installing NVIDIA drivers')
            await run_command('add-apt-repository', '-y', 'ppa:graphics-drivers')
            await run_command('apt', 'update')
            await run_command('apt', 'install', '-y', 'nvidia-390', 'nvidia-cuda-toolkit')

            installed = True

    if 'AMD' in graphics:
        display.set_step('Verifying AMD drive')
        if not is_installed('amdgpu-pro'):
            display.set_step('Installing AMD drive')
            await run_command('wget', 'https://www2.ati.com/drivers/linux/ubuntu/amdgpu-pro-18.10-572953.tar.xz', '-O', 'amdgpu-pro.tar.gz', cwd='/tmp')
            #await run_command('tar', '-xzf', 'amdgpu-pro.tar.gz', cwd='/tmp')
            #await run_command('./amdgpu-pro-install -y', cwd='/tmp/amdgpu-pro')

            #installed = True

    if installed:
        await run_command('shutdown', '-r', 'now')

    display.step_done()

    display.set_step('Verifying symlinks')
    with suppress(FileNotFoundError):
        os.remove('/etc/systemd/system/ivy.service')
    os.link(os.path.join(PATH, 'ivy.service'), '/etc/systemd/system/ivy.service')
    await run_command('systemctl', 'enable', 'ivy')

    with suppress(FileNotFoundError):
        os.remove('/etc/i3status.conf')
    os.link(os.path.join(PATH, 'i3status.conf'), '/etc/i3status.conf')

    os.makedirs(os.path.join(HOME, '.config/i3/'), exist_ok=True)
    with suppress(FileNotFoundError):
        os.remove(os.path.join(HOME, '.config/i3/config'))
    os.link(os.path.join(PATH, 'i3config.conf'), os.path.join(HOME, '.config/i3/config'))

    with suppress(FileNotFoundError):
        os.remove(os.path.join(HOME, '.Xresources'))
    os.link(os.path.join(PATH, 'Xresources'), os.path.join(HOME, '.Xresources'))

    os.makedirs('/etc/systemd/system/getty@tty1.service.d', exist_ok=True)
    with suppress(FileNotFoundError):
        os.remove('/etc/systemd/system/getty@tty1.service.d/override.conf')
    os.link(os.path.join(PATH, 'tty1@override.conf'), '/etc/systemd/system/getty@tty1.service.d/override.conf')
    display.step_done()

    await asyncio.sleep(5)

    loop.stop()

async def run_command(*args, cwd=None):
    if cwd is None:
        cwd = os.path.dirname(os.path.realpath(__file__))

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
