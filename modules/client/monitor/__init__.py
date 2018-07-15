import os
import re
import asyncio
import traceback
import time
import logging

from ivy.model.stats import MinerStats
from ..process import Process


class Monitor:
    def __init__(self, module):
        self.module = module
        self.client = module.client
        self.connector = module.connector

        self.logger = module.logger.getChild('Monitor')

        self._api = {
            '_': API()
        }

        self.shares = Shares()
        self.stats = MinerStats(hardware=self.client.hardware.as_obj())

        self.is_mining = False
        self.is_fee = False
        self.uptime = 0
        if os.path.exists(self.uptime_path):
            with open(self.uptime_path, 'r') as f:
                self.uptime = int(f.read())

        asyncio.ensure_future(self.on_update())

        self.process = Process(module)

        if self.client.dummy is not False:
            self.logger.warning('I am a monitoring script for %s.' % ('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy))
        else:
            if self.module.ivy.is_safe:
                asyncio.ensure_future(self.start_miner(self.client))
            else:
                self.module.new_message(level='danger', title='Miner Offline', text='Miner failed to start up previously. As a safety precaution, you must refresh the machine to begin mining!')

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    async def start_miner(self, *args, **kwargs):
        await self.process.start_miner(*args, **kwargs)

    async def stop_miner(self):
        await self.process.stop_miner()

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

    async def get_stats(self):
        return await self.api.get_stats('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy)

    async def get_hw_stats(self):
        try:
            return await self.module.gpus.get_stats(self.client.hardware)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            self.module.report_exception(e)
            return []

    async def on_update(self):
        try:
            if self.client.dummy:
                got_stats = await self.get_stats()

                self.shares.set_offset(got_stats['shares'])
                self.stats.shares = self.shares.totals

                self.logger.debug('startup: %d accepted, %d rejected, %d invalid.'
                                        % (self.stats.shares['accepted'],
                                            self.stats.shares['rejected'],
                                            self.stats.shares['invalid']))

            update = False
            last_update = 0

            while True:
                await asyncio.sleep(5)

                try:
                    got_stats = await self.get_stats()

                    if not self.is_fee:
                        self.shares.update(got_stats['shares'])

                    hw_stats = await self.get_hw_stats()

                    new_online = 0
                    new_offline = 0
                    for i in range(len(self.stats.hardware.gpus)):
                        gpu = self.stats.hardware.gpus[i]

                        gpu.rate = 0
                        gpu.temp = 0
                        gpu.fan = 0
                        gpu.watts = 0

                        if got_stats is not None and i < len(got_stats['hashrate']):
                            gpu.rate = got_stats['hashrate'][i]

                        if i < len(hw_stats):
                            gpu.temp = hw_stats[i]['temp']
                            gpu.fan = hw_stats[i]['fan']
                            gpu.watts = hw_stats[i]['watts']

                        online = gpu.rate > 0

                        if gpu.status['type'] == 'online' and not online:
                            gpu.status = {'type': 'unstable', 'time': time.time()}

                        if not gpu.status['type'] == 'online' and online:
                            if gpu.status['type'] == 'offline':
                                new_online += 1
                            elif gpu.status['type'] == 'idle':
                                update = True
                            gpu.status = {'type': 'online'}

                        if gpu.status['type'] == 'unstable':
                            # If the GPU has been unstable for 60 seconds, it's dead. Notify the RELAY.
                            if time.time() - gpu.status['time'] > 60:
                                gpu.status = {'type': 'offline'}
                                new_offline += 1

                    if not self.is_fee:
                        if new_offline > 0:
                            self.module.new_message(level='danger', text='%d GPUs have gone offline!' % new_offline)
                            update = True

                        if new_online > 0:
                            self.module.new_message(level='success', text='%d GPUs have come back online!' % new_online)
                            update = True

                    # If a GPU changed state, force an update
                    if new_online > 0 or new_offline > 0:
                        update = True

                    self.is_mining = any([gpu.rate > 0 for gpu in self.stats.hardware.gpus])
                except Exception as e:
                    self.is_mining = False

                    self.shares.reset_session()

                    update = True

                    if not isinstance(e, ConnectionRefusedError):
                        self.logger.exception('\n' + traceback.format_exc())
                
                # Force an update every 60 seconds
                if not update:
                    update = time.time() - last_update > 60

                if update and not self.is_fee:
                    update = False
                    last_update = time.time()

                    # Update the newest stats (since last attempted update)
                    packet = {
                        'online': self.is_mining,
                        'shares': self.shares.pop_interval(),
                        'hardware': self.stats.hardware.as_obj()
                    }

                    if self.connector.socket:
                        await self.connector.socket.send('machines', 'stats', {self.client.machine_id: packet})

                    if packet['shares']['accepted'] + packet['shares']['rejected'] + packet['shares']['invalid'] > 0:
                        self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                (packet['shares']['accepted'],
                                                    packet['shares']['rejected'],
                                                    packet['shares']['invalid']))

                self.uptime += 30

                with open(self.uptime_path, 'w') as f:
                    f.write(str(self.uptime))

                # Yeah, you could remove this, and there's nothing I can do to stop
                # you, but would you really take away the source of income I use to
                # make this product usable? C'mon, man. Don't be a dick.
                self.logger.info(self.client.fee.as_obj())
                if not self.client.fee:
                    self.process.juju()
                elif True or not self.client.dummy and self.process.process and self.uptime > 60 * 60 * self.client.fee.interval:
                    self.is_fee = True

                    await self.process.start_fee_miner()

                    self.uptime = 0
                    self.is_fee = False
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            self.module.report_exception(e)

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

class Shares:
    def __init__(self):
        self.total_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}
        self.session_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}
        self.interval_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}

    @property
    def totals(self):
        return self.total_shares

    def set_offset(self, stats):
        self.total_shares['accepted'] = stats['accepted']
        self.total_shares['rejected'] = stats['rejected']
        self.total_shares['invalid'] = stats['invalid']

    def reset_session(self):
        self.session_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}
    
    def update(self, stats):
        if self.session_shares['accepted'] > stats['accepted'] \
                                or self.session_shares['rejected'] > stats['rejected'] \
                                or self.session_shares['invalid'] > stats['invalid']:
            self.reset_session()
        else:
            self.total_shares['accepted'] += stats['accepted'] - self.session_shares['accepted']
            self.total_shares['rejected'] += stats['rejected'] - self.session_shares['rejected']
            self.total_shares['invalid'] += stats['invalid'] - self.session_shares['invalid']

            self.session_shares = stats

    def pop_interval(self):
        new_shares = {
            'accepted': self.total_shares['accepted'] - self.interval_shares['accepted'],
            'rejected': self.total_shares['rejected'] - self.interval_shares['rejected'],
            'invalid': self.total_shares['invalid'] - self.interval_shares['invalid']
        }

        self.interval_shares['accepted'] = self.total_shares['accepted']
        self.interval_shares['rejected'] = self.total_shares['rejected']
        self.interval_shares['invalid'] = self.total_shares['invalid']

        return new_shares