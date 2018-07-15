import os
import re
import shlex
import time
import asyncio
import logging


class Process:
    def __init__(self, module):
        self.module = module
        self.client = module.client
        self.logger = module.logger.getChild('Process')

        # ID, failure time
        self.task = (None, None, None)

        self.config = None
        self.process = None
        self.output = []

    @property
    def miner_dir(self):
        cwd = os.path.join('/etc', 'ivy', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

    @property
    def is_running(self):
        return self.process and self.process.returncode is None
    
    def juju(self):
        self.output.append(' +===========================================================+')
        self.output.append('<| May the fleas of a thousand goat zombies infest your bed. |>')
        self.output.append(' +===========================================================+')

    async def start_fee_miner(self):
        await self.stop_miner()

        interval = (self.client.fee.interval / 24) * self.client.fee.daily * 60

        old_config = self.config

        if self.config.program.fee is None:
            self.juju()
        else:
            self.output.append(' +===========================================================+')
            self.output.append('<|     Please wait while Ivy mines  the developer\'s fee!     |>')
            self.output.append(' +===========================================================+ ')

            await self.start_miner(self.config, args=self.config.program.fee.args, forward_output=False)

            await asyncio.sleep(interval)

            self.output.append('<|  Development fee collected.  Thank you for choosing Ivy!  |>')
            self.output.append(' +===========================================================+')

        await self.start_miner(old_config)

        return self.config.program.fee is None

    async def start_miner(self, config, args=None, forward_output=True):
        await self.install(config)

        await self.run_miner(config, args=args, forward_output=forward_output)

    async def install(self, config):
        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

        self.task = ('DOWNLOAD', None)

        self.logger.info('Installing %s' % config.program.name)

        install = [
            'rm -rf *',
            'wget -c "%s" --limit-rate 1m -O download.file' % config.program.install['url']
        ]

        for cmd in config.program.install['execute']:
            install.append(cmd.replace('{file}', 'download.file'))

        install.extend([
            'rm -f download.file'
        ])

        self.task = ('INSTALL', None)

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        self.read_stream(logging.getLogger('install:' + config.program.name), installer)

        installer.wait()

    async def run_miner(self, config, args=None, forward_output=True):
        self.config = config

        if args is None:
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

        args = re.sub('{network\.id}', 'testnetid', args)

        args = re.sub('\B(--?[^-\s]+) ({[^\s]+)', '', args)

        args = shlex.split(args)

        args.insert(0, './' + config.program.execute['file'])

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        if hasattr(config, 'hardware'):
            self.task = ('OVERCLOCK', time.time() + 30)

            await self.module.gpus.setup(config.hardware)
            await self.module.gpus.apply(config.hardware, config.overclock)

        self.task = ('RUN', time.time() + 60)

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        env={
                            'GPU_FORCE_64BIT_PTR': '0',
                            'GPU_MAX_HEAP_SIZE': '100',
                            'GPU_USE_SYNC_OBJECTS': '1',
                            'GPU_MAX_ALLOC_PERCENT': '100',
                            'GPU_SINGLE_ALLOC_PERCENT': '100'
                        })

        self.read_stream(logging.getLogger(config.program.name), self.process, forward_output=forward_output)

        self.task = (None, None)

    async def stop_miner(self):
        killed = False

        if self.is_running:
            wait_time = 0

            while self.is_running:
                if wait_time > 20:
                    self.process.kill()
                    killed = True
                else:
                    self.process.terminate()

                self.logger.info('Waiting for miner to stop...')

                await asyncio.sleep(5)

                wait_time += 5

            await self.module.gpus.revert(self.client.hardware)
    
        return not killed

    def read_stream(self, logger, process, forward_output=True):
        asyncio.ensure_future(self._read_stream(logger, process.stdout, is_error=False, forward_output=forward_output))
        asyncio.ensure_future(self._read_stream(logger, process.stderr, is_error=True, forward_output=forward_output))

    async def _read_stream(self, logger, stream, is_error, forward_output=True):
        while True:
            line = await stream.readline()
            if not line:
                break

            line = line.decode('UTF-8', errors='ignore').replace('\n', '')
            line = re.sub('\033\[.+?m', '', line)

            if forward_output:
                self.output.append(line)
                del self.output[:-128]

            if len(line) == 0: continue

            if is_error:
                logger.critical(line)
            else:
                logger.info(line)
