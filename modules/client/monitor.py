import asyncio
import traceback
import json
import socket


class Monitor:
    def __init__(self, logger, client, connector, process):
        self.client = client
        self.connector = connector
        self.process = process

        self.logger = logger.getChild('Monitor')

        self.output = []
        self.shares = {'accepted': 0, 'rejected': 0, 'invalid': 0}

        asyncio.ensure_future(self.ping_miner())

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    def as_obj(self):
        return {
            'config': self.process.config.as_obj() if self.process.config is not None else {},
            'hardware': self.client.hardware.as_obj(),
            'shares': self.shares,
            'output': self.output
        }

    def get_stats(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy, 3333))
        s.send('{"id": 0, "jsonrpc": "2.0", "method": "miner_getstat1"}'.encode("utf-8"))
        data = json.loads(s.recv(2048).decode("utf-8"))
        s.close()

        version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = data['result']

        runtime = int(runtime)

        eth_totals = [int(x) for x in eth_totals.split(';')]
        eth_hashrates = [int(x) for x in eth_hashrates.split(';')]

        stats = stats.split(';')
        stats = [[273.15 + float(stats[i * 2]), int(stats[i * 2 + 1])] for i in range(int(len(stats) / 2))]

        invalids = [int(x) for x in invalids.split(';')]

        return version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids

    async def ping_miner(self):
        try:
            try:
                total_shares = {'invalid': 0, 'accepted': 0, 'rejected': 0}

                if self.client.dummy:
                    version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = self.get_stats()
                    total_shares['invalid'] = invalids[0]
                    total_shares['shares']['accepted'] = eth_totals[1]
                    total_shares['shares']['rejected'] = eth_totals[2]

                if total_shares['invalid'] > 0 or total_shares['accepted'] > 0 \
                    or total_shares['rejected'] > 0:
                    self.logger.debug('startup: %d accepted, %d rejected, %d invalid.' % (total_shares['accepted'], total_shares['rejected'], total_shares['invalid']))

                uptime = 0
                if os.path.exists(self.uptime_path):
                    with open(self.uptime_path, 'r') as f:
                        uptime = int(f.read())

                update = False
                last_poke = 0

                stats = MinerStats(hardware=self.client.hardware.as_obj())

                while True:
                    await asyncio.sleep(5)

                    try:
                        uptime += 5

                        version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, gpu_stats, pools, invalids = self.get_stats()

                        stats.runtime = runtime

                        # This data should only contain the amount of change in share data
                        # since the last update for statistics purposes.
                        stats.shares['accepted'] = eth_totals[1] - total_shares['accepted']
                        stats.shares['rejected'] = eth_totals[2] - total_shares['rejected']
                        stats.shares['invalid'] = invalids[0] - total_shares['invalid']

                        new_offline = 0
                        for i in range(min(len(eth_hashrates), len(stats.hardware.gpus))):
                            gpu = stats.hardware.gpus[i]

                            online = eth_hashrates[i] > 0
                            if gpu.online and not online:
                                new_offline += 1
                            gpu.online = online

                            gpu.rate = eth_hashrates[i]
                            gpu.temp = gpu_stats[i][0]
                            gpu.fan = gpu_stats[i][1]
                            gpu.watts = 0

                        self.shares['accepted'] = stats.shares['accepted'] + total_shares['accepted']
                        self.shares['rejected'] = stats.shares['rejected'] + total_shares['rejected']
                        self.shares['invalid'] = stats.shares['invalid'] + total_shares['invalid']

                        if new_offline > 0 and self.connector.socket:
                            await self.connector.socket.send('messages', 'new', {'level': 'warning', 'text': '%d GPUs have gone offline!' % new_offline, 'machine': self.ivy.id})

                        # If the miner is offline, set it online and force an update
                        if not stats.online:
                            update = stats.online = True
                        else:
                            # Otherwise, push an update every minute
                            update = time.time() - last_poke > 60
                    except Exception as e:
                        stats.online = False
                        update = True
                        if not isinstance(e, ConnectionRefusedError):
                            self.logger.exception('\n' + traceback.format_exc())

                    if update:
                        if self.master_priority is not None and self.connector.socket:
                            await self.connector.socket.send('machines', 'stats', {self.ivy.id: stats.as_obj()})
                        else:
                            self.logger.warning('Not connected to any MASTER SERVER.')

                        total_shares['invalid'] += stats.shares['invalid']
                        total_shares['accepted'] += stats.shares['accepted']
                        total_shares['rejected'] += stats.shares['rejected']

                        if stats.shares['accepted'] + stats.shares['rejected'] + stats.shares['invalid'] > 0:
                            self.logger.info('new: %d accepted, %d rejected, %d invalid.' %
                                                    (stats.shares['accepted'],
                                                        stats.shares['rejected'],
                                                        stats.shares['invalid']))

                        update = False
                        last_poke = time.time()

                        with open(self.uptime_path, 'w') as f:
                            f.write(str(uptime))

                    # Yeah, you could remove this, and there's nothing I can do to stop
                    # you, but would you really take away the source of income I use to
                    # make this product usable? C'mon, man. Don't be a dick.
                    if not self.client.dummy and self.client.fee and uptime > 60 * 60 * self.client.fee.interval:
                        interval = self.client.fee.interval / 24 * self.client.fee.daily
                        self.logger.info('Switching to fee miner for %d seconds...' % interval)

                        await self.start(config=client.fee.config)

                        # Mine for 5 minutes
                        await asyncio.sleep(interval)

                        self.logger.info('Thanks for chosing ivy! Returning to configured miner...')

                        await self.start_miner()

                        uptime = 0
            except Exception as e:
                self.logger.exception('\n' + traceback.format_exc())
                if self.connector.socket:
                    await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': traceback.format_exc(), 'machine': self.ivy.id})
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            if self.connector.socket:
                await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': traceback.format_exc(), 'machine': self.ivy.id})
