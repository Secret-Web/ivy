class MinerStats:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.online = kwargs['online'] if 'online' in kwargs else False
        self.shares = kwargs['shares'] if 'shares' in kwargs else {'invalid': 0, 'accepted': 0, 'rejected': 0}
        self.hardware = MinerHardware(**kwargs['hardware'] if 'hardware' in kwargs else {})

    def as_obj(self):
        obj = {}

        if self.online is not None: obj['online'] = self.online
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

    def as_obj(self):
        obj = {}

        if self.gpus is not None: obj['gpus'] = [x.as_obj() for x in self.gpus]

        return obj

class GPUStats:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.online = kwargs['online'] if 'online' in kwargs else False
        self.watts = kwargs['watts'] if 'watts' in kwargs else 0
        self.temp = kwargs['temp'] if 'temp' in kwargs else 0
        self.rate = kwargs['rate'] if 'rate' in kwargs else 0
        self.fan = kwargs['fan'] if 'fan' in kwargs else 0

    def as_obj(self):
        obj = {}

        if self.online is not None: obj['online'] = self.online
        if self.watts is not None: obj['watts'] = self.watts
        if self.temp is not None: obj['temp'] = self.temp
        if self.rate is not None: obj['rate'] = self.rate
        if self.fan is not None: obj['fan'] = self.fan

        return obj
