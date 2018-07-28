from ivy.model.hardware import Hardware
from ivy.model.config import Config


class Client:
    def __init__(self, **kwargs):
        self.update(init=True, **kwargs)

    def update(self, init=False, **kwargs):
        self.machine_id = kwargs['machine_id'] if 'machine_id' in kwargs else None
        self.hardware = Hardware(**kwargs['hardware'] if 'hardware' in kwargs and kwargs['hardware'] else {})

        self.config = Config(**kwargs['config'] if 'config' in kwargs else {})

        if 'name' in kwargs or init: self.name = kwargs['name'] if 'name' in kwargs and kwargs['name'] is not None and len(kwargs['name'].strip()) > 0 else 'Unnamed Miner'
        if 'notes' in kwargs or init: self.notes = kwargs['notes'] if 'notes' in kwargs and kwargs['notes'] is not None and len(kwargs['notes'].strip()) > 0 else None

    def as_obj(self, is_client=False):
        obj = {}

        if self.hardware is not None: obj['hardware'] = self.hardware.as_obj()

        if self.config is not None: obj['config'] = self.config.as_obj(is_client=True)

        if not is_client:
            if self.name is not None: obj['name'] = self.name
            if self.notes is not None: obj['notes'] = self.notes

        return obj
