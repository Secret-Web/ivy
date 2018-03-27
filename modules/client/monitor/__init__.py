import os
import re
import asyncio
import traceback
import time

from ivy.model.stats import MinerStats


class Monitor:
    def __init__(self, module):
        self.client = module.client
        self.connector = module.connector
        self.process = module.process

        self.logger = module.logger.getChild('Monitor')

        self.output = []
        self.shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

        self.uptime = 0
        if os.path.exists(self.uptime_path):
            with open(self.uptime_path, 'r') as f:
                self.uptime = int(f.read())

        self.stats = MinerStats(hardware=self.client.hardware.as_obj())

        self._api = {
            '_': API()
        }

        asyncio.ensure_future(self.ping_miner())

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

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    def read_stream(self, logger, process, allow_log=False):
        asyncio.ensure_future(self._read_stream(logger, process.stdout, error=False, allow_log=allow_log))
        asyncio.ensure_future(self._read_stream(logger, process.stderr, error=True, allow_log=allow_log))

    async def _read_stream(self, logger, stream, error, allow_log=False):
        while True:
            line = await stream.readline()
            if line:
                line = line.decode('UTF-8', errors='ignore')
                line = re.sub('\033\[.+?m', '', line)

                self.output.append(line)
                del self.output[:-128]

                if len(line) == 0: continue

                if is_error:
                    logger.critical(line)
                    if allow_log and self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'danger', 'text': line, 'machine': self.client.machine_id})
                else:
                    logger.info(line)
            else:
                break

    async def get_stats(self):
        return await self.api.get_stats('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy)

    async def get_hw_stats(self):
        try:
            return await self.gpus.get_stats(self.client.hardware)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': str(e), 'machine': self.client.machine_id})
            return []

    async def ping_miner(self):
        try:
            updated_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

            if self.client.dummy:
                got_stats = await self.get_stats()
                updated_shares['accepted'] = got_stats['shares']['accepted']
                updated_shares['rejected'] = got_stats['shares']['rejected']
                updated_shares['invalid'] = got_stats['shares']['invalid']

                self.logger.debug('startup: %d accepted, %d rejected, %d invalid.' % (updated_shares['accepted'], updated_shares['rejected'], updated_shares['invalid']))

            update = False
            last_poke = 0

            while True:
                await asyncio.sleep(5)

                self.uptime += 5

                try:
                    got_stats = await self.get_stats()
                    hw_stats = await self.get_hw_stats()

                    self.stats.shares['accepted'] = got_stats['shares']['accepted'] - updated_shares['accepted']
                    self.stats.shares['rejected'] = got_stats['shares']['rejected'] - updated_shares['rejected']
                    self.stats.shares['invalid'] = got_stats['shares']['invalid'] - updated_shares['invalid']

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
                        if gpu.online and not online:
                            new_offline += 1
                        gpu.online = online

                    self.shares['accepted'] = self.stats.shares['accepted'] + updated_shares['accepted']
                    self.shares['rejected'] = self.stats.shares['rejected'] + updated_shares['rejected']
                    self.shares['invalid'] = self.stats.shares['invalid'] + updated_shares['invalid']

                    if new_offline > 0 and self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'warning', 'text': '%d GPUs have gone offline!' % new_offline, 'machine': self.client.machine_id})

                    # If the miner is offline, set it online and force an update
                    if not self.stats.online:
                        update = self.stats.online = True
                    else:
                        # Otherwise, push an update every minute
                        update = time.time() - last_poke > 60
                except Exception as e:
                    self.stats.online = False
                    update = True
                    if not isinstance(e, ConnectionRefusedError):
                        self.logger.exception('\n' + traceback.format_exc())

                if update:
                    if self.connector.socket:
                        await self.connector.socket.send('machines', 'stats', {self.client.machine_id: self.stats.as_obj()})
                    else:
                        self.logger.warning('Not connected to any MASTER SERVER.')

                    updated_shares['invalid'] += self.stats.shares['invalid']
                    updated_shares['accepted'] += self.stats.shares['accepted']
                    updated_shares['rejected'] += self.stats.shares['rejected']

                    if self.stats.shares['accepted'] + self.stats.shares['rejected'] + self.stats.shares['invalid'] > 0:
                        self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                (self.stats.shares['accepted'],
                                                    self.stats.shares['rejected'],
                                                    self.stats.shares['invalid']))

                    update = False
                    last_poke = time.time()

                    with open(self.uptime_path, 'w') as f:
                        f.write(str(self.uptime))

                # Yeah, you could remove this, and there's nothing I can do to stop
                # you, but would you really take away the source of income I use to
                # make this product usable? C'mon, man. Don't be a dick.
                if not self.client.dummy and self.client.fee and self.uptime > 60 * 60 * self.client.fee.interval:
                    interval = (self.client.fee.interval / 24) * self.client.fee.daily * 60
                    self.logger.info('Switching to fee miner for %d seconds...' % interval)

                    await self.process.start(config=self.client.fee.config)

                    # Mine for 5 minutes
                    await asyncio.sleep(interval)

                    self.logger.info('Thanks for chosing ivy! Returning to configured miner...')

                    await self.process.start(config=self.client)

                    self.uptime = 0
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            if self.connector.socket:
                await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': traceback.format_exc(), 'machine': self.client.machine_id})

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
