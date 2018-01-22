import asyncio
import shlex
from subprocess import Popen, PIPE
import json
import os
import time
import re
import socket
import traceback

import psutil

from ivy.module import Module
from ivy.net import NetConnector
from ivy.model.client import Client
from ivy.model.hardware import get_hardware
from ivy.model.stats import MinerStats


class ClientModule(Module):
    def on_load(self):
        self.config['hardware'] = get_hardware()
        self.config['hardware']['storage'] = []

        for disk in psutil.disk_partitions():
            usage = psutil.disk_usage(disk.mountpoint)
            self.config['hardware']['storage'].append({
                'mount': disk.device,
                'fstype': disk.fstype,
                'space': {
                    'free': usage.free,
                    'used': usage.used,
                    'total': usage.total
                }
            })
        print(self.config['hardware']['storage'])

        self.client = Client(**self.config)

        self.process = None

        self.master_priority = None
        self.connector = NetConnector(self.logger.getChild('socket'))
        self.connector.listen_event('connection', 'open')(self.event_connection_open)
        self.connector.listen_event('connection', 'closed')(self.event_connection_closed)

        self.ivy.register_listener('master')(self.on_discovery_master)
        self.register_events(self.connector)

        self.task = asyncio.Task(self.ping_miner())

        self.start_miner()

    @property
    def fee_path(self):
        return os.path.join(os.getcwd(), 'data', '.ivy-fee')

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    @property
    def miner_dir(self):
        cwd = os.path.join(os.getcwd(), 'data', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

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
            version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = self.get_stats()
            total_shares = {
                'invalid': invalids[0],
                'accepted': eth_totals[1],
                'rejected': eth_totals[2]
            }

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
                    stats.shares['invalid'] = invalids[0] - total_shares['invalid']
                    stats.shares['accepted'] = eth_totals[1] - total_shares['accepted']
                    stats.shares['rejected'] =  eth_totals[2] - total_shares['rejected']

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

                    if new_offline > 0 and self.connector.socket:
                        await self.connector.socket.send('messages', 'new', {'level': 'warning', 'text': '%d GPUs have gone offline!' % new_offline, 'miner': self.ivy.id})

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
                if not self.client.dummy and uptime > 60 * 60 * self.client.fee.interval:
                    interval = self.client.fee.interval / 24 * self.client.fee.daily
                    self.logger.info('Switching to fee miner for %d seconds...' % interval)

                    self.start_miner(config=client.fee.config)

                    # Mine for 5 minutes
                    await asyncio.sleep(interval)

                    self.logger.info('Thanks for chosing ivy! Returning to configured miner...')

                    self.start_miner()

                    uptime = 0
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
            await self.connector.socket.send('messages', 'new', {'level': 'bug', 'title': 'Miner Exception', 'text': traceback.format_exc(), 'miner': self.ivy.id})

    @property
    def is_running(self):
        return self.process and self.process.poll() is None

    def install_miner(self, config=None):
        if self.client.dummy is not False: return

        if config is None: config = self.client

        if not config.program.is_valid():
            self.logger.error('Configured program is not valid.')
            return

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if os.path.exists(miner_dir): return
        os.mkdir(miner_dir)

        self.logger.info('Installing %s' % config.program.name)

        strip_components = 0
        if 'strip_components' in config.program.install:
            strip_components = config.program.install['strip_components']

        install = [
            'rm -rf *',
            'wget -c "%s" -O "miner.tar.gz"' % config.program.install['url'],
            'tar --strip-components=%d -xzf miner.tar.gz' % strip_components,
            'rm miner.tar.gz'
        ]

        install.extend(config.program.install['execute'])

        installer = Popen(' && '.join(install), cwd=miner_dir, stdout=PIPE, stderr=PIPE, shell=True)
        installer.wait()

    def stop_miner(self):
        if self.client.dummy is not False: return

        if self.is_running:
            self.process.terminate()
            time.sleep(5)
            if self.process.poll() is None:
                self.process.kill()

    def start_miner(self, config=None):
        if self.client.dummy is not False:
            self.logger.warning('I am a monitoring script for %s.' % ('localhost' if not isinstance(self.client.dummy, str) else self.client.dummy))
            return

        if config is None: config = self.client

        if not config.program:
            self.logger.error('No program configured.')
            return

        validated = config.program.is_valid()
        if validated is not True:
            self.logger.error('Configured program is not valid. %r' % validated)
            return

        self.stop_miner()

        self.install_miner(config=config)

        args = config.program.execute['args']

        args = re.sub('(-[^-\s]+) {miner\.id}', '\\1 %s' % self.ivy.id, args)

        if config.wallet:
            args = re.sub('(-[^-\s]+) {user}', '\\1 %s' % config.wallet.address, args)

        if config.pool.endpoint is not None:
            args = re.sub('(-[^-\s]+) {pool\.url}', '\\1 %s' % (('stratum+tcp://' if config.pool.endpoint.stratum else '') + config.pool.endpoint.url), args)
            args = re.sub('(-[^-\s]+) {pool\.pass}', '' if not config.pool.endpoint.password else '\\1 %s' % config.pool.endpoint.password, args)

            args = re.sub('(-[^-\s]+) {user}', '' if not config.pool.endpoint.username else '\\1 %s' % config.pool.endpoint.username, args)

        overclock = config.group.hardware.overclock

        args = re.sub('(-[^-\s]+) {core\.mhz}', '' if not overclock.core or not overclock.core['mhz'] else '\\1 %s' % overclock.core['mhz'], args)
        args = re.sub('(-[^-\s]+) {core\.vlt}', '' if not overclock.core or not overclock.core['vlt'] else '\\1 %s' % overclock.core['vlt'], args)

        args = re.sub('(-[^-\s]+) {mem\.mhz}', '' if not overclock.mem or not overclock.mem['mhz'] else '\\1 %s' % overclock.mem['mhz'], args)
        args = re.sub('(-[^-\s]+) {mem\.vlt}', '' if not overclock.mem or not overclock.mem['vlt'] else '\\1 %s' % overclock.mem['vlt'], args)

        args = re.sub('(-[^-\s]+) {temp\.max}', '' if not overclock.temp or not overclock.temp['max'] else '\\1 %s' % overclock.temp['max'], args)
        args = re.sub('(-[^-\s]+) {fan\.min}', '' if not overclock.fan or not overclock.fan['min'] else '\\1 %s' % overclock.fan['min'], args)

        args = re.sub('(-[^-\s]+) {pwr}', '' if not overclock.pwr else '\\1 %s' % overclock.pwr, args)

        args = shlex.split(args)
        args.insert(0, './' + config.program.execute['file'])
        args.extend(['-mport', '3333'])

        print(' '.join(args))

        miner_dir = os.path.join(self.miner_dir, config.program.name)
        if not os.path.exists(miner_dir): os.mkdir(miner_dir)

        self.process = Popen(args, cwd=miner_dir, stdout=PIPE, stderr=PIPE)

    def on_discovery_master(self, protocol, service):
        if self.master_priority is None or service.payload['priority'] < self.master_priority:
            self.logger.info('Connecting to primary %r...' % service)

            self.connector.open(service.ip, service.port, {
                'Miner-ID': self.ivy.id,
                'Subscribe': {
                    'machines': ['action'],
                    'fee': ['update']
                }
            })

            self.master_priority = service.payload['priority']

    async def event_connection_open(self, packet):
        await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

    async def event_connection_closed(self, packet):
        self.master_priority = None

    def register_events(self, l):
        @l.listen_event('machines', 'action')
        async def event(packet):
            self.logger.info('Action received: %r' % packet.payload)
            if packet.payload['id'] == 'patch':
                self.client.update(**packet.payload)

                self.config.update(self.client.as_obj())
                self.ivy.save_config()
            if packet.payload['id'] == 'refresh':
                self.client.update(**packet.payload)

                await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

                self.config.update(self.client.as_obj())
                self.ivy.save_config()

                self.start_miner()

        @l.listen_event('fee', 'update')
        async def event(packet):
            self.client.fee = Fee(**packet.payload)

__plugin__ = ClientModule
