import time


class MinerStats:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.connected = False
        self.time = time.time()
        self.status = kwargs['status'] if 'status' in kwargs else {'type': 'offline', 'fee': False}
        self.shares = kwargs['shares'] if 'shares' in kwargs else {'invalid': 0, 'accepted': 0, 'rejected': 0}
        self.hardware = MinerHardware(**kwargs['hardware'] if 'hardware' in kwargs else {})
    
    def reset(self):
        self.connected = False
        self.status = {'type': 'offline', 'fee': False}
        self.hardware.reset()

    def as_obj(self):
        obj = {}

        if self.connected is not None: obj['connected'] = self.connected
        if self.time is not None: obj['time'] = self.time
        if self.status is not None: obj['status'] = self.status
        if self.shares is not None: obj['shares'] = self.shares
        if self.hardware is not None: obj['hardware'] = self.hardware.as_obj()

        return obj

class MinerHardware:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.gpus = []

        if 'gpus' in kwargs:
            for gpu in kwargs['gpus']:
                self.gpus.append(GPUStats(**gpu))

    def reset(self, **kwargs):
        for gpu in self.gpus:
            gpu.update()

    def as_obj(self):
        obj = {}

        if self.gpus is not None: obj['gpus'] = [x.as_obj() for x in self.gpus]

        return obj

class GPUStats:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.status = kwargs['status'] if 'status' in kwargs else {'type': 'idle'}
        self.watts = kwargs['watts'] if 'watts' in kwargs else 0
        self.temp = kwargs['temp'] if 'temp' in kwargs else 0
        self.fan = kwargs['fan'] if 'fan' in kwargs else 0

        self.rate = kwargs['rate'] if 'rate' in kwargs else []

    def as_obj(self):
        obj = {}

        if self.status is not None: obj['status'] = self.status
        if self.watts is not None: obj['watts'] = self.watts
        if self.temp is not None: obj['temp'] = self.temp
        if self.fan is not None: obj['fan'] = self.fan

        if self.rate is not None: obj['rate'] = self.rate

        return obj
