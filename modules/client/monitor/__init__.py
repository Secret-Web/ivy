import os
import re
import asyncio
import traceback
import time

from ivy.model.stats import MinerStats


class Monitor:
    def __init__(self, module):
        self.module = module
        self.client = module.client
        self.connector = module.connector
        self.process = module.process

        self.logger = module.logger.getChild('Monitor')

        self.output = []
        self.stats = MinerStats(hardware=self.client.hardware.as_obj())

        self._api = {
            '_': API()
        }

        asyncio.ensure_future(self.ping_miner())

        self.message_queue = asyncio.Queue()
        asyncio.ensure_future(self.process_messages())

    async def process_messages(self):
        while True:
            if not self.connector.socket:
                await asyncio.sleep(1)
                continue

            message = await self.message_queue.get()
            message['machine'] = self.client.machine_id

            await self.connector.socket.send('messages', 'new', message)

    def new_message(self, level=None, title=None, text=None):
        if level is None: raise Exception('Level not specified!')
        if text is None: raise Exception('Text not specified!')
        pack = {'level': level, 'text': text}
        if title: pack['title'] = title
        self.message_queue.put_nowait(pack)

    @property
    def api(self):
        if not self.process.config:
            return self._api['_']

        if self.process.config.program.api not in self._api:
            try:
                api_id = self.process.config.program.api
                api = __import__('modules.client.monitor.%s' % api_id, globals(), locals(), ['object'], 0)
                self._api[api_id] = api.__api__()
            except AttributeError as ae:
                self.logger.warning('Failed to load "%s" monitor. Falling back to default.' % self.process.config.program.api)
                self._api[api_id] = API()
            except ModuleNotFoundError as me:
                self.logger.warning('Failed to load "%s" monitor. Falling back to default.' % self.process.config.program.api)
                self._api[api_id] = API()
            except Exception as e:
                self.logger.warning('Failed to load "%s" monitor. Falling back to default.' % self.process.config.program.api)
                self.logger.exception('\n' + traceback.format_exc())
                self._api[api_id] = self._api['_']
        return self._api[self.process.config.program.api]

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

    async def get_stats(self):
        return await self.api.get_stats('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy)

    async def get_hw_stats(self):
        try:
            return await self.module.gpus.get_stats(self.client.hardware)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            self.new_message(level='bug', title='Miner Exception', text=str(e))
            return []

    async def ping_miner(self):
        try:
            if self.client.dummy:
                got_stats = await self.get_stats()
                self.stats.shares['accepted'] = got_stats['shares']['accepted']
                self.stats.shares['rejected'] = got_stats['shares']['rejected']
                self.stats.shares['invalid'] = got_stats['shares']['invalid']

                self.logger.debug('startup: %d accepted, %d rejected, %d invalid.'
                                        % (self.stats.shares['accepted'],
                                            self.stats.shares['rejected'],
                                            self.stats.shares['invalid']))

            update = False
            last_poke = 0

            session_shares = None
            last_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}
            new_stats = MinerStats(hardware=self.client.hardware.as_obj())

            # Has three states. True for online, False for offline, and int while it's waiting to be confirmed offline. (unstable)
            gpu_status = {}

            while True:
                await asyncio.sleep(1)

                try:
                    got_stats = await self.get_stats()

                    if not self.module.process.is_fee:
                        if session_shares is None or session_shares['accepted'] > got_stats['shares']['accepted'] \
                                                or session_shares['rejected'] > got_stats['shares']['rejected'] \
                                                or session_shares['invalid'] > got_stats['shares']['invalid']:
                            session_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}

                        # Update the total shares using the current session offset
                        self.stats.shares['accepted'] += got_stats['shares']['accepted'] - session_shares['accepted']
                        self.stats.shares['rejected'] += got_stats['shares']['rejected'] - session_shares['rejected']
                        self.stats.shares['invalid'] += got_stats['shares']['invalid'] - session_shares['invalid']

                        session_shares = got_stats['shares']

                    hw_stats = await self.get_hw_stats()

                    new_online = 0
                    new_offline = 0
                    for i in range(len(self.stats.hardware.gpus)):
                        gpu = self.stats.hardware.gpus[i]

                        gpu.rate = 0
                        gpu.temp = 0
                        gpu.fan = 0
                        gpu.watts = 0

                        if i < len(got_stats['hashrate']):
                            gpu.rate = got_stats['hashrate'][i]

                        if i < len(hw_stats):
                            gpu.temp = hw_stats[i]['temp']
                            gpu.fan = hw_stats[i]['fan']
                            gpu.watts = hw_stats[i]['watts']

                        online = gpu.rate > 0

                        if i not in gpu_status:
                            gpu_status[i] = {'type': 'starting'}

                        if gpu.online and not online:
                            # Begin timer for "confirmed dead"
                            gpu_status[i] = {'type': 'unstable', 'time': time.time()}

                        if not gpu.online and online:
                            if gpu_status[i]['type'] == 'offline':
                                new_online += 1

                            gpu_status[i] = {'type': 'online'}

                        gpu.online = online

                        if gpu_status[i]['type'] == 'unstable':
                            # If the GPU has been unstable for 60 seconds, it's dead. Notify the master.
                            if time.time() - gpu_status[i]['time'] > 60:
                                gpu_status[i] = {'type': 'offline'}
                                new_offline += 1
                    
                    if any([gpu.rate > 0 for gpu in self.stats.hardware.gpus]):
                        self.process.watchdog.ping()

                    if not self.module.process.is_fee:
                        if new_offline > 0:
                            self.new_message(level='danger', text='%d GPUs have gone offline!' % new_offline)

                        if new_online > 0:
                            self.new_message(level='success', text='%d GPUs have come back online!' % new_online)

                    # If the miner is offline, set it online and force an update
                    if not new_stats.online or new_offline > 0 or new_online > 0:
                        update = new_stats.online = True
                    else:
                        # Otherwise, push an update every minute
                        update = time.time() - last_poke > 60
                except Exception as e:
                    new_stats.online = False
                    update = True

                    if not isinstance(e, ConnectionRefusedError):
                        self.logger.exception('\n' + traceback.format_exc())

                if update:
                    update = False
                    last_poke = time.time()

                    # Update the newest stats (since last attempted update)
                    new_stats.shares['accepted'] = self.stats.shares['accepted'] - last_shares['accepted']
                    new_stats.shares['rejected'] = self.stats.shares['rejected'] - last_shares['rejected']
                    new_stats.shares['invalid'] = self.stats.shares['invalid'] - last_shares['invalid']
                    new_stats.hardware = self.stats.hardware

                    if self.connector.socket:
                        await self.connector.socket.send('machines', 'stats', {self.client.machine_id: new_stats.as_obj()})

                    if new_stats.shares['accepted'] + new_stats.shares['rejected'] + new_stats.shares['invalid'] > 0:
                        self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                (new_stats.shares['accepted'],
                                                    new_stats.shares['rejected'],
                                                    new_stats.shares['invalid']))

                    last_shares['accepted'] = self.stats.shares['accepted']
                    last_shares['rejected'] = self.stats.shares['rejected']
                    last_shares['invalid'] = self.stats.shares['invalid']

        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            
            self.new_message(level='bug', title='Miner Exception', text=traceback.format_exc())

class API:
    async def get_stats(self, host):
        return {
            'shares': {
                'accepted': 0,
                'invalid': 0,
                'rejected': 0
            },
            'hashrate': []
        }
