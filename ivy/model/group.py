from .hardware import Hardware, Overclocks


class Group:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        self.name = kwargs['name'] if 'name' in kwargs else 'Unnamed Group'

        self.algorithm = kwargs['algorithm'] if 'algorithm' in kwargs else None

        self.pool = GroupPool(**kwargs['pool'] if 'pool' in kwargs else {})
        self.wallet = kwargs['wallet'] if 'wallet' in kwargs else None
        self.program = GroupProgram(**kwargs['program'] if 'program' in kwargs else {})

        self.hardware = GroupHardware(**kwargs['hardware'] if 'hardware' in kwargs else {})

    def reset(self):
        self.update()

    def as_obj(self, is_client=False):
        obj = {}

        if self.id is not None: obj['id'] = self.id
        if self.name is not None: obj['name'] = self.name

        if not is_client:
            if self.algorithm is not None: obj['algorithm'] = self.algorithm

            if self.pool is not None: obj['pool'] = self.pool.as_obj()
            if self.wallet is not None: obj['wallet'] = self.wallet
            if self.program is not None: obj['program'] = self.program.as_obj()

            if self.hardware is not None: obj['hardware'] = self.hardware.as_obj()

        return obj

class GroupPool:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        self.endpoint = kwargs['endpoint'] if 'endpoint' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.id is not None: obj['id'] = self.id
        if self.endpoint is not None: obj['endpoint'] = self.endpoint

        return obj

class GroupProgram:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        self.execute = kwargs['execute'] if 'execute' in kwargs else {'args': None}

    def as_obj(self):
        obj = {}

        if self.id is not None: obj['id'] = self.id
        if self.execute is not None: obj['execute'] = self.execute

        return obj

class GroupHardware:
    def __init__(self, **kwargs):
        self.overclock = Overclocks(**kwargs['overclock'] if 'overclock' in kwargs else {})

    def as_obj(self):
        obj = {}

        if self.overclock is not None: obj['overclock'] = self.overclock.as_obj()

        return obj

