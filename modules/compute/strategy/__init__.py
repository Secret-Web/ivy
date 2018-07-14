import random
import string


def new_id():
    return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(8))

class Strategy:
    def __init__(self, ivy, logger):
        self.ivy = ivy

        self.logger = logger.getChild('strategy')
    
    async def on_load(self, config):
        pass
    
    async def save_snapshot(self, snap):
        pass
    
    async def on_bind(self, l):
        pass
    
    async def on_unbind(self, l):
        pass

class Query:
    def __init__(self):
        pass

    async def size(self):
        raise NotImplementedError()

    async def all(self):
        raise NotImplementedError()

    async def put(self, k, v):
        return await self.add(k, v)

    async def new(self, k, v):
        raise NotImplementedError()

    async def add(self, v):
        raise NotImplementedError()

    async def update(self, k, v):
        raise NotImplementedError()

    async def has(self, k):
        raise NotImplementedError()

    async def get(self, k):
        raise NotImplementedError()

    async def delete(self, k):
        raise NotImplementedError()