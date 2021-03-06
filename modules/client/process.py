import os
import re
import shlex
import time
import asyncio
import logging

from .api import API


class Process:
    def __init__(self, module):
        self.module = module
        self.client = module.client
        self.logger = module.logger.getChild('Process')

        self._api = {
            '_': API()
        }

        self.uptime = 0
        if os.path.exists(self.uptime_path):
            try:
                with open(self.uptime_path, 'r') as f:
                    self.uptime = int(f.read())
            except:
                pass

        self.miner_uptime = 0
        if os.path.exists(self.miner_uptime_path):
            try:
                with open(self.miner_uptime_path, 'r') as f:
                    self.miner_uptime = int(f.read())
            except:
                pass

        self.refresh_config = None

        # ID, failure time
        self.task = None

        self.config = None
        self.process = None
        self.output = []

        self.is_fee = False

        asyncio.ensure_future(self.on_update())

    def get_api(self, config):
        api_id = config.program.api if config.program else '_'

        if api_id not in self._api:
            try:
                api = __import__('modules.client.api.%s' % api_id, globals(), locals(), ['object'], 0)
                self._api[api_id] = api.__api__()
            except AttributeError as ae:
                self.logger.warning('Failed to load "%s" api. Falling back to default.' % api_id)
                self._api[api_id] = API()
            except ModuleNotFoundError as me:
                self.logger.warning('Failed to load "%s" api. Falling back to default.' % api_id)
                self._api[api_id] = API()
            except Exception as e:
                self.logger.warning('Failed to load "%s" api. Falling back to default.' % api_id)
                self.logger.exception('\n' + traceback.format_exc())
                self._api[api_id] = self._api['_']
        return self._api[api_id]

    @property
    def api(self):
        if not self.config:
            return self._api['_']
        return self.get_api(self.config)

    async def get_stats(self):
        return await self.api.get_stats('localhost' if self.config is None or not isinstance(self.config.dummy, str) else self.config.dummy)

    @property
    def uptime_path(self):
        return os.path.join('/etc', 'ivy', '.ivy-uptime')

    @property
    def miner_uptime_path(self):
        return os.path.join('/etc', 'ivy', '.miner-uptime')

    @property
    def miner_dir(self):
        cwd = os.path.join('/etc', 'ivy', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

    @property
    def is_running(self):
        return self.process and self.process.returncode is None

    @property
    def is_fee_ready(self):
        return self.config and not self.config.dummy and self.uptime > 60 * 60 * self.config.fee.interval

    def on_start(self):
        self.config = self.client.config
        self.refresh_config = self.client.config

        self.logger.info('Current uptime is %d hours. Fee mining starts every %d hours.' % (self.uptime / 60 / 60, self.config.fee.interval))

    async def on_update(self):
        while True:
            try:
                await asyncio.sleep(1)

                if self.is_fee_ready:
                    await self.run_fee_miner(self.config)

                if self.refresh_config is not None:
                    config = self.refresh_config
                    self.refresh_config = None

                    self.miner_uptime = 0

                    await self.start_miner(config)

                if self.is_running:
                    self.miner_uptime += 1

                    with open(self.miner_uptime_path, 'w') as f:
                        f.write(str(self.miner_uptime))

                    self.uptime += 1

                    with open(self.uptime_path, 'w') as f:
                        f.write(str(self.uptime))
            except Exception as e:
                self.module.report_exception(e)

    async def refresh_miner(self, config):
        self.refresh_config = config

    async def run_fee_miner(self, config):
        if self.config.fee is None or self.config.program.fee is None:
            self.logger.warning('Fee mining disabled.')
            self.output.append(' +===========================================================+')
            self.output.append('<| May the fleas of a thousand goat zombies infest your bed. |>')
            self.output.append(' +===========================================================+')
        else:
            self.logger.info('Starting fee miner...')

            self.is_fee = True

            old_config = self.config

            interval = (self.config.fee.interval / 24) * self.config.fee.daily * 60

            self.output.append(' +===========================================================+')
            self.output.append('<|     Please wait while Ivy mines  the developer\'s fee!     |>')
            self.output.append(' +===========================================================+ ')

            await self.start_miner(config, args=config.program.fee.args)

            await asyncio.sleep(interval)

            self.output.append('<|  Development fee collected.  Thank you for choosing Ivy!  |>')
            self.output.append(' +===========================================================+')

            self.is_fee = False

            self.logger.info('Fee mined. Thank you for choosing Ivy!')

            if self.refresh_config is None:
                await self.start_miner(old_config)

        self.uptime = 0

    async def start_miner(self, config, args=None):
        self.config = config

        await self.stop_miner()

        if not self.client.config.is_valid:
            self.logger.exception('Config is invalid. Is a program configured?')
            return

        await self.install(config)

        await self.run_miner(config, args=args)

    async def install(self, config):
        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

        self.task = ('DOWNLOAD PROGRAM', None)

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

        self.task = ('INSTALL PROGRAM', None)

        installer = await asyncio.create_subprocess_shell(' && '.join(install), cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        self.read_stream(logging.getLogger('install:' + config.program.name), installer)

        await installer.wait()

        self.task = None

    async def run_miner(self, config, args=None):
        self.process = None

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

        args = re.sub('{miner\.id}', config.worker_id, args)

        args = re.sub('{network\.id}', 'testnetid', args)

        args = re.sub('\B(--?[^-\s]+) ({[^\s]+)', '', args)

        args += ' ' + self.get_api(config).get_forced_args()

        args = shlex.split(args)

        args.insert(0, './' + config.program.execute['file'])

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        if config.overclock:
            self.task = ('OVERCLOCK GPUS', time.time() + 60)

            await self.module.gpus.setup(self.client.hardware)
            await self.module.gpus.apply(self.client.hardware, config.overclock)

        self.task = ('RUN PROGRAM', time.time() + 60)

        self.logger.info(' '.join(args))

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        env={
                            #'GPU_FORCE_64BIT_PTR': '0',
                            'GPU_MAX_HEAP_SIZE': '100',
                            'GPU_USE_SYNC_OBJECTS': '1',
                            'GPU_MAX_ALLOC_PERCENT': '100',
                            'GPU_SINGLE_ALLOC_PERCENT': '100'
                        })

        self.read_stream(logging.getLogger(config.program.name), self.process)

        self.task = None

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

    def read_stream(self, logger, process):
        asyncio.ensure_future(self._read_stream(logger, process.stdout, is_error=False))
        asyncio.ensure_future(self._read_stream(logger, process.stderr, is_error=True))

    async def _read_stream(self, logger, stream, is_error):
        while True:
            line = await stream.readline()
            if not line:
                break

            line = line.decode('UTF-8', errors='ignore').replace('\n', '')
            line = re.sub('\033\[.+?m', '', line)

            if not self.is_fee:
                self.output.append(line)
                del self.output[:-128]

            if len(line) == 0: continue

            if is_error:
                logger.critical(line)
            else:
                logger.info(line)
