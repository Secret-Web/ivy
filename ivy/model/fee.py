from ivy.model.pool import Pool
from ivy.model.wallet import Wallet
from ivy.model.program import Program


class Fee:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.daily = kwargs['daily'] if 'daily' in kwargs else 15
        self.interval = kwargs['interval'] if 'interval' in kwargs else 4

        self.config = FeeConfig(**kwargs['config']) if 'config' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.daily is not None: obj['daily'] = self.daily
        if self.interval is not None: obj['interval'] = self.interval

        if self.config is not None: obj['config'] = self.config.as_obj()

        return obj

class FeeConfig:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.pool = Pool(**kwargs['pool']) if 'pool' in kwargs else None
        self.wallet = Wallet(**kwargs['wallet']) if 'wallet' in kwargs else None
        self.program = Program(**kwargs['program']) if 'program' in kwargs else None

    def as_obj(self):
        obj = {}

        obj['name'] = 'Dev Mining'

        if self.pool is not None: obj['pool'] = self.pool.as_obj()
        if self.wallet is not None: obj['wallet'] = self.wallet.as_obj()
        if self.program is not None: obj['program'] = self.program.as_obj()

        return obj
