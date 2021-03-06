import os
import re
import asyncio
import traceback
import time
import logging

from ivy.model.stats import MinerStats
from ivy.net import Packet
from .process import Process


class Monitor:
    def __init__(self, module):
        self.module = module
        self.client = module.client
        self.connector = module.connector

        self.logger = module.logger.getChild('Monitor')

        self.shares = Shares()
        self.stats = MinerStats(hardware=self.client.hardware.as_obj())

        self.is_mining = False
        self.last_hash_time = None

        asyncio.ensure_future(self.on_update())

        self.process = Process(module)

        if self.client.config is None:
            self.logger.warning('Not yet configured to run a program.')
        else:
            if self.client.config.dummy is not False:
                self.logger.warning('I am a monitoring script for %s.' % ('localhost' if not isinstance(self.client.config.dummy, str) else self.client.config.dummy))
            else:
                if self.module.ivy.is_safe:
                    self.process.on_start()
                else:
                    # If the process was previously online for more than half an hour, assume it was stable
                    if self.process.miner_uptime > 60 * 30:
                        self.module.new_message(level='warning', title='Miner Offline', text='Miner failed to start up previously. However, it seemed stable before. Starting up miner...')
                        self.process.on_start()
                    else:
                        self.module.new_message(level='danger', title='Miner Offline', text='Miner failed to start up previously. As a safety precaution, you must refresh the machine to begin mining!')

    async def refresh_miner(self, config):
        await self.process.refresh_miner(config)

    async def on_stop(self):
        await self.process.stop_miner()

    async def get_hw_stats(self):
        try:
            return await self.module.gpus.get_stats(self.client.hardware)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            self.module.report_exception(e)
            return []

    async def on_update(self):
        try:
            if self.client.config.dummy:
                got_stats = await self.process.get_stats()

                self.shares.set_offset(got_stats['shares'])
                self.stats.shares = self.shares.totals

                self.logger.debug('startup: %d accepted, %d rejected, %d invalid.'
                                        % (self.stats.shares['accepted'],
                                            self.stats.shares['rejected'],
                                            self.stats.shares['invalid']))

            was_connected = False
            update = False
            last_update = 0

            while True:
                await asyncio.sleep(5)

                if self.process.task is not None:
                    task, fail_time = self.process.task

                    if time.time() > fail_time:
                        self.module.new_message(level='warning', title='Miner Frozen', text='Failed on task: %s. Rebooting system as a safety percaution.' % task)

                        if self.process.process:
                            self.process.process.kill()

                        await asyncio.sleep(5)

                        # Force a reboot through the proper channel.
                        await self.connector.call_event(Packet(self.connector.socket, 'machine', 'action', payload={'id': 'reboot'}, dummy=True))

                        return

                if self.process.process is None:
                    self.last_hash_time = time.time()
                elif self.last_hash_time is not None:
                    # If the miner has run for 5 minutes without hashing, reboot
                    if time.time() - self.last_hash_time > 60 * 5:
                        self.module.new_message(level='warning', title='Miner Frozen', text='Machine not hashing! Rebooting the system, now.')

                        if self.process.process:
                            self.process.process.kill()

                        await asyncio.sleep(5)

                        # Force a reboot through the proper channel.
                        await self.connector.call_event(Packet(self.connector.socket, 'machine', 'action', payload={'id': 'reboot'}, dummy=True))

                        return

                try:
                    got_stats = await asyncio.wait_for(self.process.get_stats(), timeout=5)

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

                    if not self.process.is_fee:
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
                    if self.is_mining:
                        self.last_hash_time = time.time()
                except Exception as e:
                    if not isinstance(e, ConnectionRefusedError):
                        self.logger.exception('\n' + traceback.format_exc())

                    self.is_mining = False
                    self.shares.reset_session()
                    self.stats.reset()

                    update = True

                # Force an update every 60 seconds
                if not update:
                    update = time.time() - last_update > 60

                if self.connector.socket:
                    if not was_connected:
                        update = True
                    was_connected = True
                else:
                    was_connected = False

                if update:
                    update = False
                    last_update = time.time()

                    # Update the newest stats (since last attempted update)
                    packet = {
                        'status': {
                            'type': 'offline' if self.process.process is None else 'online' if not self.is_mining else 'mining',
                            'fee': self.process.is_fee
                        },
                        'shares': self.shares.pop_interval(),
                        'hardware': self.stats.hardware.as_obj()
                    }

                    if self.connector.socket:
                        await self.connector.socket.send('machines', 'new_stats', {self.client.machine_id: packet})

                    if packet['shares']['accepted'] + packet['shares']['rejected'] + packet['shares']['invalid'] > 0:
                        self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                (packet['shares']['accepted'],
                                                    packet['shares']['rejected'],
                                                    packet['shares']['invalid']))
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            self.module.report_exception(e)

class Shares:
    def __init__(self):
        self.total_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}
        self.session_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}
        self.interval_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

    @property
    def totals(self):
        return self.total_shares

    def set_offset(self, stats):
        self.total_shares['accepted'] = stats['accepted']
        self.total_shares['rejected'] = stats['rejected']
        self.total_shares['invalid'] = stats['invalid']

    def reset_session(self):
        self.session_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}
    
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
