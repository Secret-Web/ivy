import random
import string


def new_id():
    return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(8))

class Strategy:
    def __init__(self, ivy, logger, config):
        self.ivy = ivy

        self.logger = logger.getChild('strategy')

        self.on_load(config)
    
    def on_load(self, config):
        pass
    
    def save_snapshot(self, snap):
        pass

class Query:
    def __init__(self):
        pass

    async def all(self):
        raise NotImplementedError()

    async def put(self, k, v):
        raise NotImplementedError()

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