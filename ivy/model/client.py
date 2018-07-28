from ivy.model.hardware import Hardware
from ivy.model.config import Config


class Client:
    def __init__(self, **kwargs):
        self.update(init=True, **kwargs)

    def update(self, init=False, **kwargs):
        if 'machine_id' in kwargs or init: self.machine_id = kwargs['machine_id'] if 'machine_id' in kwargs else None
        if 'hardware' in kwargs or init: self.hardware = Hardware(**kwargs['hardware'] if 'hardware' in kwargs and kwargs['hardware'] else {})

        if 'worker_id' in kwargs or init: self.worker_id = kwargs['worker_id'] if 'worker_id' in kwargs else None
        if 'name' in kwargs or init: self.name = kwargs['name'] if 'name' in kwargs and kwargs['name'] is not None and len(kwargs['name'].strip()) > 0 else 'Unnamed Miner'
        if 'notes' in kwargs or init: self.notes = kwargs['notes'] if 'notes' in kwargs and kwargs['notes'] is not None and len(kwargs['notes'].strip()) > 0 else None

        if 'config' in kwargs or init: self.config = Config(**kwargs['config'] if 'config' in kwargs else {})

    def as_obj(self, is_client=False):
        obj = {}

        if self.worker_id is not None: obj['worker_id'] = self.worker_id
        if self.config is not None: obj['config'] = self.config.as_obj()

        if not is_client:
            if self.name is not None: obj['name'] = self.name
            if self.notes is not None: obj['notes'] = self.notes

        return obj
