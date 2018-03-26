from ivy.model.hardware import Hardware
from ivy.model.group import Group
from ivy.model.pool import Pool
from ivy.model.wallet import Wallet
from ivy.model.program import Program
from ivy.model.fee import Fee


class Client:
    def __init__(self, **kwargs):
        self.update(init=True, **kwargs)

    def update(self, init=False, **kwargs):
        if 'machine_id' in kwargs or init: self.machine_id = kwargs['machine_id'] if 'machine_id' in kwargs else None
        if 'worker_id' in kwargs or init: self.worker_id = kwargs['worker_id'] if 'worker_id' in kwargs else None

        if 'dummy' in kwargs or init: self.dummy = kwargs['dummy'] if 'dummy' in kwargs else False
        if 'name' in kwargs or init: self.name = kwargs['name'] if 'name' in kwargs and kwargs['name'] is not None and len(kwargs['name'].strip()) > 0 else 'Unnamed Miner'
        if 'notes' in kwargs or init: self.notes = kwargs['notes'] if 'notes' in kwargs and kwargs['notes'] is not None and len(kwargs['notes'].strip()) > 0 else None

        if 'hardware' in kwargs or init:
            if not hasattr(self, 'hardware'):
                self.hardware = Hardware(**kwargs['hardware'] if 'hardware' in kwargs and kwargs['hardware'] else {})
            else:
                self.hardware.update(**kwargs['hardware'] if 'hardware' in kwargs and kwargs['hardware'] else {})

        if 'group' in kwargs or init: self.group = Group(**kwargs['group'] if 'group' in kwargs and kwargs['group'] else {})
        if 'pool' in kwargs or init: self.pool = Pool(**kwargs['pool']) if 'pool' in kwargs and kwargs['pool'] else None
        if 'wallet' in kwargs or init: self.wallet = Wallet(**kwargs['wallet']) if 'wallet' in kwargs and kwargs['wallet'] else None
        if 'program' in kwargs or init: self.program = Program(**kwargs['program']) if 'program' in kwargs and kwargs['program'] else None

        if 'fee' in kwargs or init: self.fee = Fee(**kwargs['fee']) if 'fee' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.worker_id is not None: obj['worker_id'] = self.worker_id

        if self.dummy is not None: obj['dummy'] = self.dummy
        if self.name is not None: obj['name'] = self.name
        if self.notes is not None: obj['notes'] = self.notes

        if self.hardware is not None: obj['hardware'] = self.hardware.as_obj()

        if self.group is not None: obj['group'] = self.group.as_obj()
        if self.pool is not None: obj['pool'] = self.pool.as_obj()
        if self.wallet is not None: obj['wallet'] = self.wallet.as_obj()
        if self.program is not None: obj['program'] = self.program.as_obj()

        if self.fee is not None: obj['fee'] = self.fee.as_obj()

        return obj
