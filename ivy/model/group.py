from .hardware import Hardware


class Group:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        self.name = kwargs['name'] if 'name' in kwargs else 'Unnamed Group'

        self.pool = GroupPool(**kwargs['pool'] if 'pool' in kwargs else {})
        self.wallet = kwargs['wallet'] if 'wallet' in kwargs else None
        self.program = GroupProgram(**kwargs['program'] if 'program' in kwargs else {})

        self.hardware = GroupHardware(**kwargs['hardware'] if 'hardware' in kwargs else {})

    def reset(self):
        self.update()

    def as_obj(self):
        obj = {}

        if self.id is not None: obj['id'] = self.id
        if self.name is not None: obj['name'] = self.name

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

class Overclocks:
    def __init__(self, **kwargs):
        self.nvidia = Overclock(**kwargs['nvidia'] if 'nvidia' in kwargs else {})
        self.amd = Overclock(**kwargs['amd'] if 'amd' in kwargs else {})

    def as_obj(self):
        obj = {}

        if self.nvidia is not None: obj['nvidia'] = self.nvidia.as_obj()
        if self.amd is not None: obj['amd'] = self.amd.as_obj()

        return obj

class Overclock:
    def __init__(self, **kwargs):
        self.core = kwargs['core'] if 'core' in kwargs else {'mhz': None, 'vlt': None}
        if isinstance(self.core['mhz'], str): self.core['mhz'] = None
        if isinstance(self.core['vlt'], str): self.core['vlt'] = None

        self.mem = kwargs['mem'] if 'mem' in kwargs else {'mhz': None, 'vlt': None}
        if isinstance(self.mem['mhz'], str): self.mem['mhz'] = None
        if isinstance(self.mem['vlt'], str): self.mem['vlt'] = None

        self.fan = kwargs['fan'] if 'fan' in kwargs else {'min': None}
        if isinstance(self.fan['min'], str): self.fan['min'] = None

        self.temp = kwargs['temp'] if 'temp' in kwargs else {'max': None}
        if isinstance(self.temp['max'], str): self.temp['mhz'] = None

        self.pwr = kwargs['pwr'] if 'pwr' in kwargs else None
        if isinstance(self.pwr, str): self.pwr = None

    def as_obj(self):
        obj = {}

        if self.core is not None: obj['core'] = self.core
        if self.mem is not None: obj['mem'] = self.mem

        if self.fan is not None: obj['fan'] = self.fan
        if self.temp is not None: obj['temp'] = self.temp

        if self.pwr is not None: obj['pwr'] = self.pwr

        return obj
