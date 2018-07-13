import os
import re
import shlex
import logging
import asyncio
import traceback


class Process:
    def __init__(self, module):
        self.module = module

        self.client = module.client
        self.connector = module.connector

        self.logger = module.logger.getChild('Process')

        self.watchdog = ProcessWatchdog(self.logger)

        self.config = None

        self.uptime = 0
        self.is_collecting = False
        if os.path.exists(self.uptime_path):
            with open(self.uptime_path, 'r') as f:
                self.uptime = int(f.read())

        self.is_fee = False
        self.process = None
        self.process_streams = None

        asyncio.ensure_future(self.ping_miner())

        if self.client.dummy is not False:
            self.logger.warning('I am a monitoring script for %s.' % ('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy))

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

    async def ping_miner(self):
        try:
            while True:
                await asyncio.sleep(30)

                if not self.is_running: continue

                config = self.module.client

                if not config.program:
                    self.logger.error('No program configured.')
                    return

                self.uptime += 30

                with open(self.uptime_path, 'w') as f:
                    f.write(str(self.uptime))

                # Yeah, you could remove this, and there's nothing I can do to stop
                # you, but would you really take away the source of income I use to
                # make this product usable? C'mon, man. Don't be a dick.
                if not self.client.dummy and self.client.fee and self.uptime > 60 * 60 * self.client.fee.interval:
                    self.is_fee = True

                    await self.stop()

                    interval = (self.client.fee.interval / 24) * self.client.fee.daily * 60

                    if config.program.fee is None:
                        self.module.monitor.output.append(' +===========================================================+')
                        self.module.monitor.output.append('<| May the fleas of a thousand goat zombies infest your bed. |>')
                        self.module.monitor.output.append(' +===========================================================+')
                    else:
                        self.module.monitor.output.append(' +===========================================================+')
                        self.module.monitor.output.append('<|     Please wait while Ivy mines  the developer\'s fee!     |>')
                        self.module.monitor.output.append(' +===========================================================+ ')

                        await self.start_miner(config, args=config.program.fee.args, forward_output=False)

                        self.is_collecting = True

                        await asyncio.sleep(interval)

                        if not self.is_collecting:
                            continue
                        self.is_collecting = False

                        self.module.monitor.output.append('<|  Development fee collected.  Thank you for choosing Ivy!  |>')
                        self.module.monitor.output.append(' +===========================================================+')

                    self.uptime = 0
                    self.is_fee = False

                    await self.start()
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            
            self.module.monitor.new_message(level='bug', title='Miner Exception', text=traceback.format_exc())

    async def start(self):
        config = self.module.client

        if not config.program:
            self.logger.error('No program configured.')
            return

        await self.stop()

        await self.install(config=config)

        await self.start_miner(config, config.program.execute['args'])

    async def start_miner(self, config, args, forward_output=True):
        self.watchdog.init()

        # If this is the first time a process was started, and Ivy
        # did not gracefully shut down then assume this boot is unsafe.
        if self.watchdog.first_start and not self.module.ivy.is_safe:
            self.watchdog.is_safe = False

        if not self.watchdog.is_safe:
            self.module.monitor.new_message(level='danger', title='Startup Failure', text='Miner failed to start up previously. As a safety precaution, you must refresh the machine to begin mining!')
            return
        
        return

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
            await self.module.gpus.apply(config.hardware, self.client.group.hardware.overclock)

        self.logger.info('Starting miner: %s' % ' '.join(args))

        self.process = await asyncio.create_subprocess_exec(*args, cwd=miner_dir,
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        self.module.monitor.read_stream(logging.getLogger(config.program.name), self.process, forward_output=forward_output)

        self.watchdog.startup_complete()

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

        self.module.monitor.read_stream(logging.getLogger('Install'), installer)

        await installer.wait()

    async def stop(self):
        self.is_collecting = False

        if self.is_running:
            wait_time = 0

            while self.is_running:
                if wait_time > 30:
                    self.process.kill()
                else:
                    self.process.terminate()

                self.logger.info('Waiting for miner to stop...')

                await asyncio.sleep(5)

                wait_time += 5

            await self.module.gpus.revert(self.client.hardware)

            self.watchdog.cleanup()

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

    def ping(self):
        if not self.online:
            self.logger.info('Process successfully started')

        self.online = True

        self.cleanup()

    def cleanup(self):
        if os.path.exists(STARTING_UP_INDICATOR):
            os.remove(STARTING_UP_INDICATOR)
