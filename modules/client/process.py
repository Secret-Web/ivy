import os
import re
import shlex
import logging
import asyncio

from .gpu import GPUControl
from .monitor import Monitor


class Process:
    def __init__(self, logger, client, connector):
        self.client = client
        self.connector = connector

        self.logger = logger.getChild('Process')

        self.gpus = GPUControl()
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

    async def start(self, config):
        if not config.program:
            self.logger.error('No program configured.')
            return

        await self.stop()

        self.config = config

        await self.install(config=config)

        args = config.program.execute['args']

        args = re.sub('{miner\.id}', '%s' % self.client.worker_id, args)

        if config.wallet:
            args = re.sub('{user}', '%s' % config.wallet.address, args)

        if config.pool.endpoint is not None:
            if config.pool.endpoint.url:
                ignore_stratum = config.program.execute['ignore_stratum'] if 'ignore_stratum' in config.program.execute else False
                args = re.sub('{pool\.url}', '%s' % (('stratum+tcp://' if config.pool.endpoint.stratum and not ignore_stratum else '') + config.pool.endpoint.url), args)

                if ':' in config.pool.endpoint.url:
                    args = re.sub('{pool\.url\.host}', '%s' % (('stratum+tcp://' if config.pool.endpoint.stratum and not ignore_stratum else '') + config.pool.endpoint.url.split(':')[0]), args)
                    args = re.sub('{pool\.url\.port}', '%s' % config.pool.endpoint.url.split(':')[1], args)

            if config.pool.endpoint.password:
                args = re.sub('{pool\.pass}', '' if not config.pool.endpoint.password else '%s' % config.pool.endpoint.password, args)

            if config.pool.endpoint.username:
                args = re.sub('{user}', '' if not config.pool.endpoint.username else '%s' % config.pool.endpoint.username, args)

        args = re.sub('{miner\.id}', self.client.worker_id, args)

        args = re.sub('\B(--?[^-\s]+) ({[^\s<]+)', '', args)

        args = shlex.split(args)
        args.insert(0, './' + config.program.execute['file'])

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        await self.gpus.setup()
        await self.gpus.apply(config.hardware, self.client.group.hardware.overclock)

        self.logger.info('Starting miner...')

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        logger = logging.getLogger(config.program.name)
        asyncio.ensure_future(self._read_stream(logger, self.process.stdout, error=False))
        asyncio.ensure_future(self._read_stream(logger, self.process.stderr, error=True))

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

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir, bufsize=0,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await installer.wait()

    async def stop(self):
        if self.is_running:
            self.logger.info('Stopping miner...')

            self.process.terminate()

            await self.gpus.revert(self.client.hardware)

            await asyncio.sleep(5)
            if self.is_running is None:
                self.process.kill()

    async def _read_stream(self, logger, stream, error):
        while True:
            line = await stream.readline()
            if line:
                is_error = b'\033[0;31m' in line
                line = line.decode('UTF-8', errors='ignore').strip()
                line = re.sub('\033\[.+?m', '', line)

                self.monitor.output.append(line)
                del self.monitor.output[:-128]

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
            else:
                break
