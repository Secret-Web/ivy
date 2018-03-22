import os
import re
import shlex
import logging
import asyncio

from . import gpu_control
from .monitor import Monitor


class Process:
    def __init__(self, logger, client, connector):
        self.client = client
        self.connector = connector

        self.logger = logger.getChild('Process')

        self.monitor = Monitor(self.logger, client, connector, self)

        self.process = None
        self.config = None

    @property
    def miner_dir(self):
        cwd = os.path.join(os.getcwd(), 'data', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

    @property
    def is_running(self):
        return self.process and self.process.returncode is None

    async def install(self, config):
        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

        self.logger.info('Installing %s' % config.program.name)

        strip_components = 0
        if 'strip_components' in config.program.install:
            strip_components = config.program.install['strip_components']

        install = [
            'rm -rf *',
            'wget -c "%s" -O "miner.tar.gz"' % config.program.install['url'],
            'tar --strip-components=%d -xzf miner.tar.gz' % strip_components,
            'rm miner.tar.gz'
        ]

        install.extend(config.program.install['execute'])

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await installer.wait()

    async def stop(self):
        if self.is_running:
            self.process.terminate()

            await gpu_control.revert(self.client.hardware)

            await asyncio.sleep(5)
#            if self.process.poll() is None:
#                self.process.kill()

    async def start(self, config):
        if not config.program:
            self.logger.error('No program configured.')
            return

        await self.stop()

        self.config = config

        await self.install(config=config)

        args = config.program.execute['args']

        args = re.sub('(-[^-\s]+) {miner\.id}', '\\1 %s' % self.client.worker_id, args)

        if config.wallet:
            args = re.sub('(-[^-\s]+) {user}', '\\1 %s' % config.wallet.address, args)

        if config.pool.endpoint is not None:
            args = re.sub('(-[^-\s]+) {pool\.url}', '\\1 %s' % (('stratum+tcp://' if config.pool.endpoint.stratum else '') + config.pool.endpoint.url), args)
            args = re.sub('(-[^-\s]+) {pool\.pass}', '' if not config.pool.endpoint.password else '\\1 %s' % config.pool.endpoint.password, args)

            args = re.sub('(-[^-\s]+) {user}', '' if not config.pool.endpoint.username else '\\1 %s' % config.pool.endpoint.username, args)

        args = re.sub('{miner\.id}', self.client.worker_id, args)

        args = shlex.split(args)
        args.insert(0, './' + config.program.execute['file'])

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        await gpu_control.setup()
        await gpu_control.apply(config.hardware, self.client.group.hardware.overclock)

        print(' '.join(args))

        logger = logging.getLogger(config.program.name)
        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        asyncio.ensure_future(self._read_stream(logger, self.process.stdout, error=False))
        asyncio.ensure_future(self._read_stream(logger, self.process.stderr, error=True))

    async def _read_stream(self, logger, stream, error):
        while True:
            print('waiting')
            line = await stream.readline()
            print('line')
            if line:
                is_error = b'\033[0;31m' in line
                line = line.decode('UTF-8', errors='ignore').strip()
                line = re.sub('\033\[.+?m', '', line)

                if len(line) == 0: continue

                if is_error:
                    logger.critical(line)
                    if self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'danger', 'text': line, 'machine': self.client.machine_id})
                elif error:
                    logger.error(line)
                    if self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'warning', 'text': line, 'machine': self.client.machine_id})
                else:
                    logger.info(line)

                self.monitor.output.append(line)

                del self.monitor.output[:-128]

                print('appended')
            else:
                break
