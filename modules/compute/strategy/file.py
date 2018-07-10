import os
import json
import asyncio
from shutil import copyfile

from ivy.model.message import Message
from ivy.model.pool import Pool
from ivy.model.wallet import Wallet
from ivy.model.group import Group
from ivy.model.client import Client

from . import new_id, Strategy, Query


class DictQuery:
    def __init__(self, clazz, data: dict):
        self.clazz = clazz
        self.data = {k: self.clazz(**v) for k, v in data.items()}

    async def all(self):
        for k, v in self.data.items():
            yield (k, v)

    async def put(self, k, v):
        if not isinstance(v, self.clazz):
            v = self.clazz(**v)

        self.data[k] = v
        return k, v

    async def new(self, v):
        return await self.add(new_id(), v)

    async def add(self, k, v):
        if not isinstance(v, self.clazz):
            v = self.clazz(**v)

        self.data[k] = v
        return k, v

    async def update(self, kv):
        changed = {}

        for k, v in kv.items():
            k, v = await self.put(k, v)
            changed[k] = v

        return changed

    async def has(self, k):
        return k in self.data

    async def get(self, k):
        return self.data[k]

    def delete(self, k):
        del self.data[k]

class ListQuery:
    def __init__(self, clazz, data: list):
        self.clazz = clazz
        self.data = [self.clazz(**v) for v in data]
    
    async def all(self):
        for v in self.data:
            yield v

    async def put(self, k, v):
        if not isinstance(v, self.clazz):
            v = self.clazz(**v)

        self.data.insert(k, v)

    async def new(self, v):
        return await self.add(0, v)

    async def add(self, k, v):
        if not isinstance(v, self.clazz):
            v = self.clazz(**v)

        self.data[k] = v
        return k, v

    async def has(self, v):
        return v in self.data

    async def get(self, k):
        return self.data[k]

    async def delete(self, k):
        del self.data[k]

class FileStrategy(Strategy):
    def on_load(self, config):
        loaded = {}
        if os.path.exists(self.database_file):
            with open(self.database_file, 'r') as f:
                try:
                    loaded = json.load(f)
                except:
                    self.logger.error('Failed to decode database file! Trying backup...')
                    with open(self.database_file_backup, 'r') as ff:
                        try:
                            loaded = json.load(ff)
                        except:
                            self.logger.error('Failed to decode database file backup! Settings destroyed! Sorry!')

        self.messages = [Message(**x) for x in loaded['messages']] if 'messages' in loaded else []
        self.pools = {k: Pool(**v) for k, v in loaded['pools'].items()} if 'pools' in loaded else {}
        self.wallets = {k: Wallet(**v) for k, v in loaded['wallets'].items()} if 'wallets' in loaded else {}
        self.groups = {k: Group(**v) for k, v in loaded['groups'].items()} if 'groups' in loaded else {}
        self.machines = {k: Client(**v) for k, v in loaded['machines'].items()} if 'machines' in loaded else {}

        self.messages = ListQuery(Message, loaded['messages'] if 'messages' in loaded else [])
        self.pools = DictQuery(Pool, loaded['pools'] if 'pools' in loaded else {})
        self.wallets = DictQuery(Wallet, loaded['wallets'] if 'wallets' in loaded else {})
        self.groups = DictQuery(Group, loaded['groups'] if 'groups' in loaded else {})
        self.machines = DictQuery(Client, loaded['machines'] if 'machines' in loaded else {})

        asyncio.ensure_future(self.periodic_save())

    @property
    def database_file(self):
        return os.path.join('/etc', 'ivy', 'database.json')

    @property
    def database_file_backup(self):
        return os.path.join('/etc', 'ivy', 'database.json.bak')

    async def periodic_save(self):
        last_update = 0

        while True:
            # Wait 5 seconds between each save
            await asyncio.sleep(5)

            obj = {}

            obj['messages'] = [x.as_obj() async for x in self.messages.all()]
            obj['pools'] = {k: v.as_obj() async for k, v in self.pools.all()}
            obj['wallets'] = {k: v.as_obj() async for k, v in self.wallets.all()}
            obj['groups'] = {k: v.as_obj() async for k, v in self.groups.all()}
            obj['machines'] = {k: v.as_obj() async for k, v in self.machines.all()}

            if os.path.exists(self.database_file_backup):
                os.remove(self.database_file_backup)

            if os.path.exists(self.database_file):
                copyfile(self.database_file, self.database_file_backup)

            with open(self.database_file, 'w') as f:
                f.write(json.dumps(obj, indent=2))

    async def save_snapshot(self, snapshot):
        pass

__strategy__ = FileStrategy