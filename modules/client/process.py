import os
import re
import shlex
import time
import logging
import asyncio
import traceback


class Process:
    def __init__(self, module):
        self.module = module

        self.client = module.client

        self.logger = module.logger.getChild('Process')

        # self.watchdog = ProcessWatchdog(self.logger)
        self.first_run = True
        self.is_mining = False

        self.config = None

        self.uptime = 0
        self.is_collecting = False
        if os.path.exists(self.uptime_path):
            with open(self.uptime_path, 'r') as f:
                self.uptime = int(f.read())

        self.is_fee = False
        self.process = None
        self.process_streams = None

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    @property
    def miner_dir(self):
        cwd = os.path.join('/etc', 'ivy', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

    @property
    def is_running(self):
        return self.process and self.process.returncode is None

    async def start_miner(self, config, args, forward_output=True):
        if self.first_run and not self.module.ivy.is_safe:
            self.first_run = False

            raise Exception('Miner failed to start up previously. As a safety precaution, you must refresh the machine to begin mining!')

        self.first_run = False
        self.is_mining = False

        self.config = config

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
            await self.module.gpus.setup(config.hardware)
            await self.module.gpus.apply(config.hardware, config.overclock)

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        env={
                            'GPU_FORCE_64BIT_PTR': '0',
                            'GPU_MAX_HEAP_SIZE': '100',
                            'GPU_USE_SYNC_OBJECTS': '1',
                            'GPU_MAX_ALLOC_PERCENT': '100',
                            'GPU_SINGLE_ALLOC_PERCENT': '100'
                        })

    async def install(self, config):
        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

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

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        return installer

    async def stop(self):
        self.is_collecting = False

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

STARTING_UP_INDICATOR = '/etc/ivy/.process-starting-up'

class ProcessWatchdog:
    def __init__(self, logger):
        self.logger = logger.getChild('Watchdog')

        self.first_start = True
        self.is_safe = True

        self.online = False

    def init(self):
        self.online = False

        self.is_safe = not os.path.exists(STARTING_UP_INDICATOR)

        open(STARTING_UP_INDICATOR, 'a').close()

        self.logger.info('Detected an ungraceful shutdown of the process.')

    def startup_complete(self):
        self.first_start = False

        self.logger.info('Process starting up. Waiting for success confirmation.')

    def startup_failure(self):
        self.first_start = False

        self.logger.info('Process startup failed.')

        self.cleanup()

    def ping(self):
        if not self.online:
            self.logger.info('Process successfully started')

        self.online = True

        self.cleanup()

    def cleanup(self):
        if os.path.exists(STARTING_UP_INDICATOR):
            os.remove(STARTING_UP_INDICATOR)
