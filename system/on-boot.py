
import sys
import os
import re
import asyncio
from asyncio.subprocess import PIPE, STDOUT


step_i = 0
steps_max = 0
with open(__file__, 'r') as f:
	steps_max = f.read().count('step_done()') - 2

def step_done():
	step_i += 1

async def system_check():
	print('Checking for system patches')
	await run_command('apt', 'update')
	await run_command('apt', 'upgrade', '-y')
	await run_command('apt', 'autoremove', '-y')
	step_done()

	print('Installing tools')
	await run_command('apt', 'install', '-y', *'libcurl4-openssl-dev libssl-dev libjansson-dev automake autotools-dev build-essential'.split(' '))
	await run_command('apt', 'install', '-y', 'gcc-5', 'g++-5')
	await run_command('update-alternatives', '--install', '/usr/bin/gcc', 'gcc', '/usr/bin/gcc-5', '1')
	await run_command('apt', 'install', '-y', 'software-properties-common')
	await run_command('apt', 'install', '-y', *'lshw ocl-icd-opencl-dev libcurl4-openssl-dev'.split(' '))
	step_done()

	print('Installing XOrg + i3')
	await run_command('apt', 'install', '-y', 'xorg', 'i3', 'chromium-browser')
	await run_command('systemctl', 'set-default', 'multi-user.target')
	await run_command('usermod', '-a', '-G', 'video', 'ivy')
	step_done()

	print('Installing python requirements')
	await run_command(sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt')
	step_done()

	print('Verifying graphics drivers')
	await asyncio.sleep(2)
	step_done()

	print('Verifying symlinks')
	await run_command('rm', '-f', '/etc/systemd/system/ivy-boot.service')
	await run_command('ln', '-f', '/home/ivy/ivy/system/ivy-boot.service', '/etc/systemd/system/ivy-boot.service')
	await run_command('systemctl', 'enable', 'ivy-boot')

	await run_command('rm', '-f', '/etc/systemd/system/ivy.service')
	await run_command('ln', '-f', '/home/ivy/ivy/system/ivy.service', '/etc/systemd/system/ivy.service')
	await run_command('systemctl', 'enable', 'ivy')

	await run_command('rm', '-f', '/etc/i3status.conf')
	await run_command('ln', '-f', '/home/ivy/ivy/system/i3status.conf', '/etc/i3status.conf')

	await run_command('mkdir', '-p', '/home/ivy/.config/i3/')
	await run_command('rm', '-f', '/home/ivy/.config/i3/config')
	await run_command('ln', '-f', '/home/ivy/ivy/system/i3config.conf', '/home/ivy/.config/i3/config')

	await run_command('rm', '-f', '/home/ivy/.Xresources')
	await run_command('ln', '-f', '/home/ivy/ivy/system/Xresources.conf', '/home/ivy/.Xresources')

	await run_command('mkdir', '/etc/systemd/system/getty@tty1.service.d')
	await run_command('rm', '-f', '/etc/systemd/system/getty@tty1.service.d/override.conf')
	await run_command('ln', '-f', '/home/ivy/ivy/system/tty1@override.conf', '/etc/systemd/system/getty@tty1.service.d/override.conf')
	step_done()

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
	print('[%d / %d] %s' % (step_i, steps_max, output))

loop = asyncio.get_event_loop()

loop.run_until_complete(system_check())
