from ivy.model.hardware import Hardware, Overclocks
from ivy.model.group import Group
from ivy.model.pool import Pool
from ivy.model.wallet import Wallet
from ivy.model.program import Program
from ivy.model.fee import Fee


class Config:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.dummy = kwargs['dummy'] if 'dummy' in kwargs else False

        self.group = Group(**kwargs['group'] if 'group' in kwargs and kwargs['group'] else {})
        self.pool = Pool(**kwargs['pool']) if 'pool' in kwargs and kwargs['pool'] else None
        self.wallet = Wallet(**kwargs['wallet']) if 'wallet' in kwargs and kwargs['wallet'] else None
        self.program = Program(**kwargs['program']) if 'program' in kwargs and kwargs['program'] else None
        self.overclock = Overclocks(**kwargs['overclock'] if 'overclock' in kwargs else {})
        
        self.fee = Fee(**kwargs['fee'] if 'fee' in kwargs else {})

    def as_obj(self, is_client=False):
        obj = {}

        if self.dummy is not None: obj['dummy'] = self.dummy

        if self.group is not None: obj['group'] = self.group.as_obj(is_client=is_client)
        if self.pool is not None: obj['pool'] = self.pool.as_obj()
        if self.wallet is not None: obj['wallet'] = self.wallet.as_obj()
        if self.program is not None: obj['program'] = self.program.as_obj()
        if self.overclock is not None: obj['overclock'] = self.overclock.as_obj()

        if self.fee is not None: obj['fee'] = self.fee.as_obj()

        return obj
