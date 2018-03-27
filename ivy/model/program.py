from ivy.model.pool import Pool
from ivy.model.wallet import Wallet


class Program:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.name = kwargs['name'] if 'name' in kwargs else None
        self.url = kwargs['url'] if 'url' in kwargs else None
        self.support = kwargs['support'] if 'support' in kwargs else None
        self.algorithm = kwargs['algorithm'] if 'algorithm' in kwargs else None
        self.other = kwargs['other'] if 'other' in kwargs else None

        self.api = kwargs['api'] if 'api' in kwargs else None
        self.execute = kwargs['execute'] if 'execute' in kwargs else {'file': None, 'args': None}
        self.install = kwargs['install'] if 'install' in kwargs else {'url': None, 'execute': None}

        self.fee = FeeConfig(**kwargs['fee']) if 'fee' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.name is not None: obj['name'] = self.name
        if self.url is not None: obj['url'] = self.url
        if self.support is not None: obj['support'] = self.support
        if self.algorithm is not None: obj['algorithm'] = self.algorithm
        if self.other is not None: obj['other'] = self.other

        if self.api is not None: obj['api'] = self.api
        if self.execute is not None: obj['execute'] = self.execute
        if self.install is not None: obj['install'] = self.install

        if self.fee is not None: obj['fee'] = self.config.as_obj()

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
