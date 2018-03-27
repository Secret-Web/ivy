import os
import re
import shlex
import logging
import asyncio


class Process:
    def __init__(self, module):
        self.module = module

        self.client = module.client
        self.connector = module.connector

        self.logger = module.logger.getChild('Process')

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

        await self.install(config=config)

        args = config.program.execute['args']

        if config.wallet:
            args = re.sub('{user}', '%s' % config.wallet.address, args)

        if config.program.algorithm:
            args = re.sub('{algorithm}', '%s' % config.program.algorithm.lower(), args)

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

        await self.start_miner(config, shlex.split(args))

    async def start_miner(self, config, args, log=False):
        args.insert(0, './' + config.program.execute['file'])

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        if hasattr(config, 'hardware'):
            await self.module.gpus.setup()
            await self.module.gpus.apply(config.hardware, self.client.group.hardware.overclock)

        self.logger.info('Starting miner: %s' % ' '.join(args))

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        self.module.monitor.read_stream(logging.getLogger(config.program.name), self.process, allow_log=True)

    async def install(self, config):
        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

        self.logger.info('Installing %s' % config.program.name)

        install = [
            'rm -rf *',
            'wget -c "%s" -O download.file' % config.program.install['url']
        ]

        for cmd in config.program.install['execute']:
            install.append(cmd.replace('{file}', 'download.file'))

        install.extend([
            'rm -f download.file'
        ])

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        self.module.monitor.read_stream(logging.getLogger('Install'), installer, allow_log=False)

        await installer.wait()

    async def stop(self):
        if self.is_running:
            while self.is_running:
                self.process.terminate()

                self.logger.info('Waiting for miner to stop...')
                await asyncio.sleep(5)

            await self.module.gpus.revert(self.client.hardware)
