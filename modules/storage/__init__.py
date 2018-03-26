import asyncio
import copy
import random
import string
import traceback
from datetime import datetime, timedelta

from wakeonlan import send_magic_packet

from epyphany import Service
from ivy.module import Module
from ivy.net import NetConnector
from ivy.model.client import Client
from ivy.model.stats import MinerStats
from ivy.model.pool import Pool, PoolEndpoint
from ivy.model.wallet import Wallet
from ivy.model.program import Program
from ivy.model.group import Group
from ivy.model.message import Message

from .database import Database
from . import database, statistics

# TODO: Currently, 'patch'es aren't consumed by secondary storage services. This needs to be fixed.

def new_id():
    return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(8))

class StorageModule(Module):
    def on_load(self):
        if 'type' not in self.config:
            self.config['type'] = 'file'

        self.database = Database(self.logger)
        self.stats = statistics.Store()

        self.master_priority = None
        self.connector = NetConnector(self.logger.getChild('socket'))
        self.connector.listen_event('connection', 'closed')(self.event_connection_closed)

        self.ivy.register_listener('master')(self.on_discovery_master)
        self.register_events(self.connector)

        self.task = asyncio.ensure_future(self.update())

    async def update(self):
        while True:
            try:
                await asyncio.sleep(60 * 60)

                await self.connector.socket.send('coins', 'data', self.database.coins)
                await self.connector.socket.send('tickers', 'data', self.database.tickers)

                '''if len(self.machines) > IMMEDIATE_STAT_CUTOFF:
                    all_stats = {}

                    for id, miner in self.database.machines.items():
                        all_stats[id] = miner['stats']

                    # Batch notify listeners of miner stats
                    await packet.reply('machines', 'stats', all_stats)'''
            except Exception as e:
                self.logger.exception('\n' + traceback.format_exc())

    def new_snapshot(self, snapshot):
        try:
            self.stats.save(snapshot)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())

    def on_discovery_master(self, protocol, service):
        if self.master_priority is None or service.payload['priority'] < self.master_priority:
            self.logger.info('Connecting to primary %r...' % service)
            self.connector.open(service.ip, service.port, {
                'Subscribe': {
                    'connection': ['*'],

                    'coins': ['*'],
                    'tickers': ['*'],
                    'messages': ['*'],

                    'software': ['*'],
                    'fee': ['*'],

                    'pools': ['*'],
                    'wallets': ['*'],

                    'groups': ['*'],
                    'machines': ['*'],
                    'machine': ['*'],
                    'miner': ['*'],
                    'stats': ['query']
                }
            })

            self.master_priority = service.payload['priority']

    async def event_connection_closed(self, packet):
        if packet.dummy:
            self.master_priority = None

    def register_events(self, l):
        @l.listen_event('connection', 'open')
        async def event(packet):
            # String ID indicates it's a mining rig.
            if isinstance(packet.sender, str):
                if packet.sender in self.database.machines:
                    self.database.stats[packet.sender] = MinerStats(online=True)

        @l.listen_event('connection', 'closed')
        async def event(packet):
            # String ID indicates it's a mining rig.
            if isinstance(packet.sender, str):
                if packet.sender in self.database.stats:
                    stats = self.database.stats[packet.sender]
                    stats.online = False
                    stats.runtime = 0

                    for gpu in stats.hardware.gpus:
                        gpu.update()

                    await packet.send('machines', 'stats', {packet.sender: self.database.stats[packet.sender].as_obj()})

        @l.listen_event('stats', 'query')
        async def event(packet):
            stats = self.stats.get_statistics(packet.payload['start'] if 'start' in packet.payload else None,
                                                packet.payload['end'] if 'end' in packet.payload else datetime.utcnow(),
                                                increment=packet.payload['increment'] if 'increment' in packet.payload else None,
                                                machine=packet.payload['machine'] if 'machine' in packet.payload else None)
            await packet.reply('stats', 'response', payload={'id': packet.payload['id'], 'data': stats})


        @l.listen_event('software', 'get')
        async def event(packet):
            await packet.reply('software', 'data', self.database.software)

        @l.listen_event('coins', 'get')
        async def event(packet):
            await packet.reply('coins', 'data', self.database.coins)

        @l.listen_event('tickers', 'get')
        async def event(packet):
            await packet.reply('tickers', 'data', self.database.tickers)


        @l.listen_event('fee', 'get')
        async def event(packet):
            await packet.reply('fee', 'data', self.database.fee.as_obj())

        @l.listen_event('fee', 'set')
        async def event(packet):
            packet.payload['daily'] = int(packet.payload['daily'])
            if not packet.payload['daily'] < 15:
                self.database.fee.daily = packet.payload['daily']

            packet.payload['interval'] = int(packet.payload['interval'])
            if not (packet.payload['interval'] < 1 or packet.payload['interval'] > 24):
                self.database.fee.interval = packet.payload['interval']

            await packet.send('fee', 'data', self.database.fee.as_obj())

        @l.listen_event('messages', 'get')
        async def event(packet):
            await packet.reply('messages', 'data', [x.as_obj() for x in self.database.messages])

        @l.listen_event('messages', 'new')
        async def event(packet):
            await new_message(packet, packet.payload)

        @l.listen_event('messages', 'delete')
        async def event(packet):
            del self.database.messages[packet.payload if packet.payload else 0]
            await packet.send('messages', 'data', [x.as_obj() for x in self.database.messages])

        @l.listen_event('messages', 'data')
        async def event(packet):
            self.database.messages = packet.payload

        @l.listen_event('wallets', 'get')
        async def event(packet):
            await packet.reply('wallets', 'data', {k: v.as_obj() for k, v in self.database.wallets.items()})

        @l.listen_event('wallets', 'new')
        async def event(packet):
            id = new_id()
            self.database.wallets[id] = Wallet(**packet.payload)
            await packet.send('wallets', 'patch', {id: self.database.wallets[id].as_obj()})

        @l.listen_event('wallets', 'delete')
        async def event(packet):
            del self.database.wallets[packet.payload]
            await packet.send('wallets', 'data', {k: v.as_obj() for k, v in self.database.wallets.items()})

        @l.listen_event('wallets', 'update')
        async def event(packet):
            for id, wallet in packet.payload.items():
                self.database.wallets[id] = Wallet(**wallet)
            await packet.send('wallets', 'patch', {id: self.database.wallets[id].as_obj() for id in packet.payload})


        @l.listen_event('pools', 'get')
        async def event(packet):
            await packet.reply('pools', 'data', {k: v.as_obj() for k, v in self.database.pools.items()})

        @l.listen_event('pools', 'new')
        async def event(packet):
            id = new_id()
            self.database.pools[id] = Pool(**packet.payload)
            await packet.send('pools', 'patch', {id: self.database.pools[id].as_obj()})

        @l.listen_event('pools', 'delete')
        async def event(packet):
            del self.database.pools[packet.payload]
            await packet.send('pools', 'data', {k: v.as_obj() for k, v in self.database.pools.items()})

        @l.listen_event('pools', 'update')
        async def event(packet):
            for id, pool in packet.payload.items():
                self.database.pools[id] = Pool(**pool)
            await packet.send('pools', 'patch', {id: self.database.pools[id].as_obj() for id in packet.payload})

        @l.listen_event('pools', 'new_endpoint')
        async def event(packet):
            self.database.pools[packet.payload['id']].endpoints[new_id()] = PoolEndpoint(**packet.payload)
            await packet.send('pools', 'patch', {packet.payload['id']: self.database.pools[packet.payload['id']].as_obj()})

        @l.listen_event('pools', 'delete_endpoint')
        async def event(packet):
            del self.database.pools[packet.payload['pool_id']].endpoints[packet.payload['id']]
            await packet.send('pools', 'patch', {packet.payload['pool_id']: self.database.pools[packet.payload['pool_id']].as_obj()})


        @l.listen_event('groups', 'get')
        async def event(packet):
            await packet.reply('groups', 'data', {k: v.as_obj() for k, v in self.database.groups.items()})

        @l.listen_event('groups', 'new')
        async def event(packet):
            id = new_id()
            group = Group(**packet.payload)
            self.database.groups[id] = group
            await packet.send('groups', 'patch', {id: group.as_obj()})

            await new_message(packet, {'level': 'info', 'text': 'A new group was created: %s' % group.name, 'group': id})

        @l.listen_event('groups', 'update')
        async def event(packet):
            for id, group in packet.payload.items():
                self.database.groups[id] = Group(**group)
            await packet.send('groups', 'patch', {id: self.database.groups[id].as_obj() for id in packet.payload})

        @l.listen_event('groups', 'delete')
        async def event(packet):
            updated_machines = {}

            for id, miner in self.database.machines.items():
                if miner.group.id == packet.payload:
                    miner.group.reset()
                    updated_machines[id] = miner.as_obj()

            group = self.database.groups[packet.payload]

            del self.database.groups[packet.payload]
            await packet.send('groups', 'data', {k: v.as_obj() for k, v in self.database.groups.items()})

            if len(updated_machines) > 0:
                await packet.send('machines', 'patch', updated_machines)

                await new_message(packet, {'level': 'warning', 'text': 'A group was deleted: %s. %d machines have been ejected!' % (group.name, len(updated_machines))})
            else:
                await new_message(packet, {'level': 'warning', 'text': 'A group was deleted: %s' % group.name})

        @l.listen_event('groups', 'action')
        async def event(packet):
            updated_machines = {}

            for group_id, action in packet.payload.items():
                if action['id'] == 'upgrade':
                    if group_id == '*':
                        await new_message(packet, {'level': 'warning', 'text': 'All groups instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version'])})
                    else:
                        await new_message(packet, {'level': 'warning', 'text': 'Group instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version']), 'group': group_id})

                for id, miner in self.database.machines.items():
                    # * indicates an update to ALL group's machines.
                    if group_id == '*' or miner.group.id == group_id:
                        if action['id'] == 'wake':
                            send_magic_packet(miner.hardware.mac)
                            continue

                        await packet.send('machine', 'action', build_action(id, action), to=id)

                        if action['id'] == 'refresh':
                            updated_machines[id] = miner.as_obj()

            if len(updated_machines) > 0:
                await packet.send('machines', 'patch', updated_machines)

        @l.listen_event('machines', 'get')
        async def event(packet):
            await packet.reply('machines', 'data', {k: v.as_obj() for k, v in self.database.machines.items()})
            await packet.reply('machines', 'stats', {k: v.as_obj() for k, v in self.database.stats.items()})

        @l.listen_event('machines', 'action')
        async def event(packet):
            for id, action in packet.payload.items():
                if action['id'] == 'wake':
                    if id in self.database.machines:
                        send_magic_packet(self.database.machines[id].hardware.mac)
                    continue

                if action['id'] == 'upgrade':
                    await new_message(packet, {'level': 'warning', 'text': 'Machine instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version']), 'machine': id})

                await packet.send('machine', 'action', build_action(id, action), to=id)
            await packet.send('machines', 'patch', {id: self.database.machines[id].as_obj() for id, action in packet.payload.items() if action['id'] == 'refresh'})

        @l.listen_event('machines', 'update')
        async def event(packet):
            for id, data in packet.payload.items():
                miner = Client(**data)

                # If the group no longer exists, set it back to default
                if miner.group.id not in self.database.groups:
                    miner.group.reset()

                self.database.machines[id] = miner

                # The update was pushed by a non-miner. Patch the miner's configuration.
                if isinstance(packet.sender, int):
                    await packet.send('machine', 'action', build_action(id, {'id': 'patch'}), to=id)
            await packet.send('machines', 'patch', {id: self.database.machines[id].as_obj() for id in packet.payload})

        @l.listen_event('machines', 'stats')
        async def event(packet):
            updated_stats = {}

            print(packet)

            for id, stats in packet.payload.items():
                if id not in self.database.stats:
                    self.database.stats[id] = MinerStats(**stats)
                else:
                    self.database.stats[id].update(**stats)
                updated_stats[id] = self.database.stats[id].as_obj()

            if len(updated_stats) > 0:
                await packet.send('machines', 'stats', updated_stats)
                self.new_snapshot(updated_stats)

        async def new_message(packet, data):
            if isinstance(data, dict):
                msg = Message(**data)
                self.database.messages.insert(0, msg)
                await packet.send('messages', 'patch', [msg.as_obj()])
            elif isinstance(data, list):
                for d in data:
                    new_message(packet, d)

        def build_action(id, action):
            # The 'patch' action alters miner configuration without restarting
            # the mining script. It should only change data that doesn't directly
            # affect the script, but it is possible.

            # The 'refresh' action pushes a new configuration for the miner
            # to start mining with.

            if action['id'] == 'upgrade':
                return action

            miner = self.database.machines[id]

            data = {'id': action['id']}

            if action['id'] == 'patch':
                data['name'] = miner.name
                data['notes'] = miner.notes

                group_id = miner.group.id if miner.group else None
                if group_id in self.database.groups:
                    group = self.database.groups[group_id].as_obj()
                    group['id'] = group_id

                    data['group'] = group
            elif action['id'] == 'refresh':
                coin = None

                group_id = miner.group.id if miner.group else None

                if group_id in self.database.groups:
                    group = self.database.groups[group_id]

                    if group.pool.id in self.database.pools:
                        pool = self.database.pools[group.pool.id]

                        if group.pool.endpoint in pool.endpoints:
                            pool = {
                                'name': pool.name,
                                'endpoint': pool.endpoints[group.pool.endpoint].as_obj()
                            }

                            if 'crypto' in pool['endpoint']:
                                coin = pool['endpoint']['crypto']

                            data['pool'] = pool

                    if group.wallet in self.database.wallets:
                        wallet = self.database.wallets[group.wallet].as_obj()

                        if 'crypto' in wallet:
                            coin = wallet['crypto']

                        data['wallet'] = wallet

                    if group.program is not None and group.program.id in self.database.software:
                        program = Program(id=group.program.id, **self.database.software[group.program.id]).as_obj()

                        program['algorithm'] = self.database.coins[coin]['algorithm'] if coin is not None else None
                        program['execute']['args'] = group.program.execute['args']

                        data['program'] = program

                    group = group.as_obj()
                    group['id'] = group_id

                    data['group'] = group

                fee = self.database.fee.as_obj()
                fee['config'] = self.database.fee_configs[coin] if coin in self.database.fee_configs else self.database.fee_configs['ETH']

                data['fee'] = fee
            return data

__plugin__ = StorageModule
