import os
import asyncio
import traceback
import time

from ivy.model.stats import MinerStats


class Monitor:
    def __init__(self, logger, client, connector, process):
        self.client = client
        self.connector = connector
        self.process = process

        self.logger = logger.getChild('Monitor')

        self.output = []
        self.shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

        self.uptime = 0
        if os.path.exists(self.uptime_path):
            with open(self.uptime_path, 'r') as f:
                self.uptime = int(f.read())

        self.queued_stats = MinerStats(hardware=self.client.hardware.as_obj())

        self._api = {}

        asyncio.ensure_future(self.ping_miner())

    @property
    def api(self):
        if self.process.config.program.api not in self._api:
            try:
                api_id = self.process.config.program.api
                api = __import__('modules.client.api.%s' % api_id, globals(), locals(), ['object'], 0)
                self._api[api_id] = api.__api__()
            except:
                self._api[api_id] = API()
        return self._api[self.process.config.program.api]

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    def as_obj(self):
        return {
            'config': self.process.config.as_obj() if self.process.config is not None else {},
            'hardware': self.queued_stats.hardware.as_obj(),
            'shares': self.shares,
            'output': self.output
        }

    async def get_stats(self):
        return await self.api.get_stats('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy)

    async def ping_miner(self):
        try:
            updated_shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

            if self.client.dummy:
                stats = await self.get_stats()
                updated_shares['accepted'] = stats['shares']['accepted']
                updated_shares['rejected'] = stats['shares']['rejected']
                updated_shares['invalid'] = stats['shares']['invalid']

                self.logger.debug('startup: %d accepted, %d rejected, %d invalid.' % (updated_shares['accepted'], updated_shares['rejected'], updated_shares['invalid']))

            update = False
            last_poke = 0

            while True:
                await asyncio.sleep(5)

                self.uptime += 5

                try:
                    stats = await self.get_stats()

                    self.queued_stats.shares['accepted'] = stats['shares']['accepted'] - updated_shares['accepted']
                    self.queued_stats.shares['rejected'] = stats['shares']['rejected'] - updated_shares['rejected']
                    self.queued_stats.shares['invalid'] = stats['shares']['invalid'] - updated_shares['invalid']

                    new_offline = 0
                    for i in range(len(self.queued_stats.hardware.gpus)):
                        gpu = self.queued_stats.hardware.gpus[i]

                        gpu.rate = 0
                        gpu.temp = 0
                        gpu.fan = 0
                        gpu.watts = 0

                        if i < len(stats['hashrate']):
                            gpu.rate = stats['hashrate'][i]

                        online = gpu.rate > 0
                        if gpu.online and not online:
                            new_offline += 1
                        gpu.online = online

                    self.shares['accepted'] = self.queued_stats.shares['accepted'] + updated_shares['accepted']
                    self.shares['rejected'] = self.queued_stats.shares['rejected'] + updated_shares['rejected']
                    self.shares['invalid'] = self.queued_stats.shares['invalid'] + updated_shares['invalid']

                    if new_offline > 0 and self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'warning', 'text': '%d GPUs have gone offline!' % new_offline, 'machine': self.client.machine_id})

                    # If the miner is offline, set it online and force an update
                    if not self.queued_stats.online:
                        update = self.queued_stats.online = True
                    else:
                        # Otherwise, push an update every minute
                        update = time.time() - last_poke > 60
                except Exception as e:
                    self.queued_stats.online = False
                    update = True
                    if not isinstance(e, ConnectionRefusedError):
                        self.logger.exception('\n' + traceback.format_exc())

                if update:
                    if self.connector.socket:
                        await self.connector.socket.send('machines', 'stats', {self.client.machine_id: self.queued_stats.as_obj()})
                    else:
                        self.logger.warning('Not connected to any MASTER SERVER.')

                    updated_shares['invalid'] += self.queued_stats.shares['invalid']
                    updated_shares['accepted'] += self.queued_stats.shares['accepted']
                    updated_shares['rejected'] += self.queued_stats.shares['rejected']

                    if self.queued_stats.shares['accepted'] + self.queued_stats.shares['rejected'] + self.queued_stats.shares['invalid'] > 0:
                        self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                (self.queued_stats.shares['accepted'],
                                                    self.queued_stats.shares['rejected'],
                                                    self.queued_stats.shares['invalid']))

                    update = False
                    last_poke = time.time()

                    with open(self.uptime_path, 'w') as f:
                        f.write(str(self.uptime))

                # Yeah, you could remove this, and there's nothing I can do to stop
                # you, but would you really take away the source of income I use to
                # make this product usable? C'mon, man. Don't be a dick.
                if not self.client.dummy and self.client.fee and self.uptime > 60 * 60 * self.client.fee.interval:
                    interval = self.client.fee.interval / 24 * self.client.fee.daily
                    self.logger.info('Switching to fee miner for %d seconds...' % interval)

                    await self.process.start(config=self.client.fee.config)

                    # Mine for 5 minutes
                    await asyncio.sleep(interval)

                    self.logger.info('Thanks for chosing ivy! Returning to configured miner...')

                    await self.process.start()

                    self.uptime = 0
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            if self.connector.socket:
                await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': traceback.format_exc(), 'machine': self.client.machine_id})

class API:
    async def get_stats(self, host):
        '''

            Should return the following:
            {
                'shares': {
                    'acccepted': 0,
                    'invalid': 0,
                    'rejected': 0
                },
                'hashrate': [
                    per GPU
                ]
            }

        '''
        return {
            'shares': {
                'acccepted': 0,
                'invalid': 0,
                'rejected': 0
            },
            'hashrate': []
        }
