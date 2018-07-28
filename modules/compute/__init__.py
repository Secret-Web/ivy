import asyncio
import copy
import random
import string
import traceback
import time
from datetime import datetime, timedelta

from wakeonlan import send_magic_packet

from epyphany import Service
from ivy.module import Module
from ivy.model.client import Client
from ivy.model.config import Config
from ivy.model.stats import MinerStats
from ivy.model.pool import Pool, PoolEndpoint
from ivy.model.wallet import Wallet
from ivy.model.program import Program
from ivy.model.group import Group
from ivy.model.message import Message

from .database import Database

# TODO: Currently, 'patch'es aren't consumed by secondary storage services. This needs to be fixed.

IMMEDIATE_STAT_CUTOFF = 100

def new_id():
    return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(8))

class ComputeModule(Module):
    def on_load(self):
        if 'database' not in self.config:
            self.config['database'] = {'type': 'file'}
        if 'type' not in self.config['database']:
            self.config['database'] ['type'] = 'file'

        self.database = Database(self.ivy, self.logger, self.connector, self.config['database'])

        self.register_events(self.connector)

        asyncio.ensure_future(self.update())
    
    async def update(self):
        last_refresh = time.time()

        while True:
            try:
                await asyncio.sleep(60)

                if time.time() - last_refresh > 60 * 60:
                    await self.connector.socket.send('coins', 'data', self.database.coins)
                    await self.connector.socket.send('tickers', 'data', self.database.tickers)
                    await self.connector.socket.send('software', 'data', self.database.software)

                # Reset miners that have taken more than 10 minutes to update their stats
                for id, stats in self.database.stats.items():
                    if not stats.connected: continue

                    if time.time() - stats.time > 60 * 10:
                        self.database.stats[id].reset()

                        await self.new_message({'level': 'danger', 'text': 'Watchdog detected an idle miner. Did it freeze?', 'machine': id})

                # Batch notify listeners of miner stats
                if len(self.database.stats) >= IMMEDIATE_STAT_CUTOFF:
                    await packet.reply('machines', 'stats', {k: v.as_obj() for k, v in self.data.stats.items()})
            except Exception as e:
                self.logger.exception('\n' + traceback.format_exc())

    def on_connect_relay(self, service):
        self.connector.open(service.ip, service.port, {
            'Subscribe': {
                'connection': ['*'],

                'coins': ['*'],
                'tickers': ['*'],
                'software': ['*'],
                'fee': ['*'],

                'messages': ['*'],
                'pools': ['*'],
                'wallets': ['*'],
                'groups': ['*'],
                'machines': ['*'],

                'machine': ['*'],
                'miner': ['*'],
                'stats': ['query']
            }
        })

    def register_events(self, l):
        @l.listen_event('connection', 'open')
        async def event(packet):
            if not packet.dummy and 'Miner-ID' in packet.payload['headers']:
                miner_id = packet.payload['headers']['Miner-ID']

                stats = MinerStats(online=True)
                stats.connected = True
                self.database.stats[miner_id] = stats

        @l.listen_event('connection', 'closed')
        async def event(packet):
            if not packet.dummy and 'Miner-ID' in packet.payload['headers']:
                miner_id = packet.payload['headers']['Miner-ID']

                if miner_id in self.database.stats:
                    stats = self.database.stats[miner_id]

                    stats.reset()

                    if len(self.database.stats) < IMMEDIATE_STAT_CUTOFF:
                        await packet.send('machines', 'stats', {miner_id: stats.as_obj()})

        @l.listen_event('stats', 'query')
        async def event(packet):
            stat_id = packet.payload['id']
            del packet.payload['id']

            stats = await self.database.get_statistics(**packet.payload)
            
            await packet.reply('stats', 'response', payload={'id': stat_id, 'data': stats})


        for thing in ['software', 'coins', 'tickers', 'fee']:
            def inner(thing):
                @l.listen_event(thing, 'get')
                async def event(packet):
                    data = getattr(self.database, thing)

                    if not hasattr(data, 'as_obj'):
                        await packet.reply(thing, 'data', data)
                    else:
                        await packet.reply(thing, 'data', data.as_obj())
            inner(thing)

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
            await packet.reply('messages', 'data', [x.as_obj() async for x in self.database.messages.all()])

        @l.listen_event('messages', 'new')
        async def event(packet):
            await self.new_message(packet, packet.payload)

        @l.listen_event('messages', 'delete')
        async def event(packet):
            if packet.payload is None or isinstance(packet.payload, int):
                await self.database.messages.delete(packet.payload if packet.payload else 0)
            elif isinstance(packet.payload, str):
                o = 0
                for i in range(0, await self.database.messages.size()):
                    if (await self.database.messages.get(i - o)).level == packet.payload:
                        await self.database.messages.delete(i - o)
                        o += 1
            else:
                return

            await packet.send('messages', 'data', [x.as_obj() async for x in self.database.messages.all()])


        for thing in ['wallets', 'pools']:
            def inner(thing):
                @l.listen_event(thing, 'get')
                async def event(packet):
                    all = None

                    async for x in getattr(self.database, thing).all():
                        if isinstance(x, tuple):
                            if all is None:
                                all = {}
                            all[x[0]] = x[1].as_obj()
                        else:
                            if all is None:
                                all = []
                            all.append(x.as_obj())

                    await packet.reply(thing, 'data', all)

                @l.listen_event(thing, 'new')
                async def event(packet):
                    id, v = await getattr(self.database, thing).new(packet.payload)

                    await packet.send(thing, 'patch', {id: v.as_obj()})

                @l.listen_event(thing, 'delete')
                async def event(packet):
                    await getattr(self.database, thing).delete(packet.payload)

                    await packet.send(thing, 'patch', {packet.payload: None})

                @l.listen_event(thing, 'update')
                async def event(packet):
                    changed = await getattr(self.database, thing).update(packet.payload)

                    await packet.send(thing, 'patch', {id: v for id, v in changed.items()})

            inner(thing)


        @l.listen_event('pools', 'new_endpoint')
        async def event(packet):
            pool = await self.database.pools.get(packet.payload['id'])
            pool.endpoints[new_id()] = PoolEndpoint(**packet.payload)
            await packet.send('pools', 'patch', {packet.payload['id']: pool.as_obj()})

        @l.listen_event('pools', 'delete_endpoint')
        async def event(packet):
            pool = await self.database.pools.get(packet.payload['id'])
            del pool.endpoints[packet.payload['id']]
            await packet.send('pools', 'patch', {packet.payload['pool_id']: pool.as_obj()})


        @l.listen_event('groups', 'get')
        async def event(packet):
            await packet.reply('groups', 'data', {k: v.as_obj() async for k, v in self.database.groups.all()})

        @l.listen_event('groups', 'new')
        async def event(packet):
            id, group = await self.database.groups.new(packet.payload)
            await packet.send('groups', 'patch', {id: group.as_obj()})

            await self.new_message(packet, {'level': 'info', 'text': 'A new group was created: %s' % group.name, 'group': id})

        @l.listen_event('groups', 'delete')
        async def event(packet):
            updated_machines = {}

            async for id, miner in self.database.machines.all():
                if miner.group.id == packet.payload:
                    miner.group.reset()
                    updated_machines[id] = miner.as_obj()

            group = await self.database.groups.get(packet.payload)

            await self.database.groups.delete(packet.payload)
            await packet.send('groups', 'patch', {packet.payload: None})

            if len(updated_machines) > 0:
                await packet.send('machines', 'patch', updated_machines)

                await self.new_message(packet, {'level': 'warning', 'text': 'A group was deleted: %s. %d machines have been ejected!' % (group.name, len(updated_machines))})
            else:
                await self.new_message(packet, {'level': 'warning', 'text': 'A group was deleted: %s' % group.name})

        @l.listen_event('groups', 'update')
        async def event(packet):
            changed = await self.database.groups.update(packet.payload)
            await packet.send('groups', 'patch', {id: group.as_obj() for id, group in changed.items()})

        @l.listen_event('groups', 'action')
        async def event(packet):
            self.logger.info('group action: %r' % packet.payload)

            for group_id, action in packet.payload.items():
                await self.send_action(packet, action, group_id=group_id)


        @l.listen_event('machines', 'get')
        async def event(packet):
            await packet.reply('machines', 'data', {k: v.as_obj() async for k, v in self.database.machines.all()})
            await packet.reply('machines', 'stats', {k: v.as_obj() for k, v in self.database.stats.items()})

        @l.listen_event('machines', 'update')
        async def event(packet):
            updated_machines = {}

            for id, data in packet.payload.items():
                client = None

                if await self.database.machines.has(id):
                    # This update was pushed by a miner. Discard the group setting.
                    #if not isinstance(packet.sender, int):
                    #    del data['config']

                    client = await self.database.machines.get(id)
                else:
                    client = Client()
                
                client.update(**data)

                # If the group no longer exists, set it back to default
                if not await self.database.groups.has(client.group.id):
                    client.group.reset()

                await self.database.machines.put(id, client)

                # The update was pushed by a non-miner. Patch the miner's configuration.
                if isinstance(packet.sender, int):
                    await self.send_action(packet, {'id': 'patch'}, machine_id=id)

        @l.listen_event('machines', 'action')
        async def event(packet):
            self.logger.info('machine action: %r' % packet.payload)

            for id, action in packet.payload.items():
                if action['id'] == 'upgrade':
                    await self.new_message(packet, {'level': 'warning', 'text': 'Machine instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version']), 'machine': id})

                await self.send_action(packet, action, machine_id=id)

        @l.listen_event('machines', 'stats')
        async def event(packet):
            for id, data in packet.payload.items():
                if id not in self.database.stats:
                    stats = MinerStats(**data)
                    stats.connected = True
                    self.database.stats[id] = stats
                else:
                    stats = self.database.stats[id]
                    stats.update(**data)
                    stats.connected = True

        @l.listen_event('machines', 'new_stats')
        async def event(packet):
            updated_stats = {}

            for id, data in packet.payload.items():
                if id not in self.database.stats:
                    stats = MinerStats(**data)
                    stats.connected = True
                    self.database.stats[id] = stats
                else:
                    stats = self.database.stats[id]
                    stats.update(**data)
                    stats.connected = True
                updated_stats[id] = self.database.stats[id]

            if len(updated_stats) > 0:
                await self.database.save_snapshot(updated_stats)

                if len(self.database.stats) < IMMEDIATE_STAT_CUTOFF:
                    await packet.send('machines', 'stats', {k: v.as_obj() for k, v in updated_stats.items()})

    async def new_message(self, packet, data):
        if isinstance(data, dict):
            id, msg = await self.database.messages.new(data)
            await packet.send('messages', 'patch', [msg.as_obj()])
        elif isinstance(data, list):
            for d in data:
                self.new_message(packet, d)

    async def send_action(self, packet, action, machine_id=None, group_id=None):
        # The 'patch' action alters miner configuration without restarting
        # the mining script. It should only change data that doesn't directly
        # affect the script, but it is possible.

        # The 'refresh' action pushes a new configuration for the miner
        # to start mining with.

        if not machine_id and not group_id:
            raise Exception('No destination specified for the action.')
        if machine_id and group_id:
            raise Exception('Only one destination may be specified for the action.')

        machines = {}

        if machine_id:
            machines[machine_id] = await self.database.machines.get(machine_id)
        else:
            async for machine_id, machine in self.database.machines.all():
                if group_id == '*' or machine.group.id == group_id:
                    machines[machine_id] = machine

        if action['id'] == 'wake':
            for machine_id, machine in machines.items():
                send_magic_packet(machine.hardware.mac)
            return

        if action['id'] == 'reboot' or action['id'] == 'shutdown' or action['id'] == 'upgrade':
            if action['id'] == 'upgrade':
                if group_id == '*':
                    await self.new_message(packet, {'level': 'warning', 'text': 'All groups instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version'])})
                elif group_id:
                    await self.new_message(packet, {'level': 'warning', 'text': 'Group instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version']), 'group': group_id})
                else:
                    await self.new_message(packet, {'level': 'warning', 'text': 'Machine instructed to upgrade to %s %s.' % (action['version']['name'], action['version']['version']), 'machine': machine_id})

            for machine_id, machine in machines.items():
                await packet.send('machine', 'action', action, to=machine_id)

            return

        groups = {}
        async def get_group(group_id):
            if group_id not in groups:
                if await self.database.groups.has(group_id):
                    groups[group_id] = await self.database.groups.get(group_id)
                else:
                    groups[group_id] = None
            return groups[group_id]

        if action['id'] == 'patch':
            for machine_id, machine in machines.items():
                data = {}

                data['name'] = machine.name
                data['notes'] = machine.notes

                group_id = machine.group.id if machine.group else None
                group = await get_group(group_id)
                if group is not None:
                    data['group'] = {**group.as_obj(), **{'id': group_id}}
                
                await packet.send('machine', 'action', {**data, **{'id': action['id']}}, to=machine_id)
            return
        
        group_data = {}
        async def get_group_data(group_id):
            if group_id not in group_data:
                group = await get_group(group_id)
                if group is None:
                    group_data[group_id] = None
                    return None

                coin = None
                data = {}

                data['group'] = group.as_obj(slim=True)
                data['overclock'] = group.hardware.overclock.as_obj()

                if await self.database.pools.has(group.pool.id):
                    pool = await self.database.pools.get(group.pool.id)

                    if group.pool.endpoint in pool.endpoints:
                        pool = {
                            'name': pool.name,
                            'endpoint': pool.endpoints[group.pool.endpoint].as_obj()
                        }

                        if 'crypto' in pool['endpoint']:
                            coin = pool['endpoint']['crypto']

                        data['pool'] = pool

                if await self.database.wallets.has(group.wallet):
                    wallet = (await self.database.wallets.get(group.wallet)).as_obj()

                    if 'crypto' in wallet:
                        coin = wallet['crypto']

                    data['wallet'] = wallet

                if group.program is not None and group.program.id in self.database.software:
                    program = Program(id=group.program.id, **self.database.software[group.program.id]).as_obj()

                    program['algorithm'] = self.database.coins[coin]['algorithm'] if coin is not None else None
                    program['execute']['args'] = group.program.execute['args']

                    data['program'] = program

                fee = self.database.fee.as_obj()
                fee['config'] = self.database.fee_configs[coin] if coin in self.database.fee_configs else self.database.fee_configs['ETH']
                data['fee'] = fee

                group_data[group_id] = Config(**data)
            return group_data[group_id]

        if action['id'] == 'refresh':
            for machine_id, machine in machines.items():
                machine_group_id = machine.group.id if machine.group else None

                await packet.send('machine', 'action', {**await get_group_data(machine_group_id), **{'id': 'refresh'}}, to=machine_id)
            return

__plugin__ = ComputeModule
