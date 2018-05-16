import sys
import os
import re
import asyncio
from asyncio.subprocess import PIPE, STDOUT

import urwid


palette = [
    ('header', '', '', '', '#FFF,bold', '#558'),
    ('footer', '', '', '', '#FFF,bold', '#558'),

    ('background', '', '', '', '#FFF', '#000'),

    ('log', '', '', '', '#888', '#000'),

    ('progress-normal', '', '', '', '#FFF', '#55C'),
    ('progress-complete', '', '', '', '#000', '#FFF'),
    ('progress-smooth', '', '', '', '#CCC', '#888')
]

class Display:
    def __init__(self, loop):
        self.step_i = -1
        self.steps_max = 0
        with open(__file__, 'r') as f:
            self.steps_max = f.read().count('set_step(') - 3

        self.operation = urwid.Text('', align='center')

        self.step_text = urwid.Text('', align='center')

        self.progress = urwid.ProgressBar('progress-normal', 'progress-complete', 0, 1, 'progress-smooth')

        self.branding = urwid.Text('- SecretWeb.com -', align='center')

        self.set_step('Getting ready')
        self.step_done()

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

    def set_step(self, text):
        self.operation.set_text(text)

    def step_done(self):
        self.step_i += 1

        self.step_text.set_text('%d / %d' % (self.step_i, self.steps_max))
        self.progress.set_completion(self.step_i / self.steps_max)

    def run(self):
        self.urwid.run()

async def system_check():
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
    await run_command('apt', 'install', '-y', 'xorg', 'i3', 'chromium-browser')
    await run_command('systemctl', 'set-default', 'multi-user.target')
    await run_command('usermod', '-a', '-G', 'video', 'ivy')
    display.step_done()

    display.set_step('Installing python requirements')
    await run_command(sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt')
    display.step_done()

    display.set_step('Verifying graphics drivers')
    await asyncio.sleep(2)
    display.step_done()

    display.set_step('Verifying symlinks')
    await run_command('rm', '-f', '/etc/systemd/system/ivy-boot.service')
    await run_command('ln', '-f', './ivy-boot.service', '/etc/systemd/system/ivy-boot.service')
    await run_command('systemctl', 'enable', 'ivy-boot')

    await run_command('rm', '-f', '/etc/systemd/system/ivy.service')
    await run_command('ln', '-f', './ivy.service', '/etc/systemd/system/ivy.service')
    await run_command('systemctl', 'enable', 'ivy')

    await run_command('rm', '-f', '/etc/i3status.conf')
    await run_command('ln', '-f', './i3status.conf', '/etc/i3status.conf')

    await run_command('mkdir', '-p', '~/.config/i3/')
    await run_command('rm', '-f', '~/.config/i3/config')
    await run_command('ln', '-f', './i3config.conf', '~/.config/i3/config')

    await run_command('rm', '-f', '~/.Xresources')
    await run_command('ln', '-f', '~/ivy/system/Xresources.conf', '~/.Xresources')

    await run_command('mkdir', '/etc/systemd/system/getty@tty1.service.d')
    await run_command('rm', '-f', '/etc/systemd/system/getty@tty1.service.d/override.conf')
    await run_command('ln', '-f', './tty1@override.conf', '/etc/systemd/system/getty@tty1.service.d/override.conf')
    display.step_done()

    await asyncio.sleep(5)

    loop.stop()

async def run_command(*args):
    process = await asyncio.subprocess.create_subprocess_exec(*args, \
                                    cwd=os.path.dirname(os.path.realpath(__file__)), \
                                    stdin=PIPE, stdout=PIPE, stderr=PIPE)

    asyncio.ensure_future(_read_stream(process.stdout, is_error=False))
    asyncio.ensure_future(_read_stream(process.stderr, is_error=True))

    return await process.wait()

async def _read_stream(stream, is_error):
    while True:
        output = await stream.readline()
        if not output: break

        output = re.sub('\033\[.+?m', '', output.decode('UTF-8', errors='ignore')).replace('\n', '')
        display.output_lines.append(urwid.Text(output))
        display.output_lines.set_focus(len(display.output_lines) - 1)

loop = asyncio.get_event_loop()

loop.create_task(system_check())

display = Display(loop=loop)

#loop.run_until_complete(system_check())

display.run()
