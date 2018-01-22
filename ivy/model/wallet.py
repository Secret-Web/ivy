class Wallet:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.crypto = kwargs['crypto'] if 'crypto' in kwargs else None
        self.name = kwargs['name'] if 'name' in kwargs else None
        self.address = kwargs['address'] if 'address' in kwargs else None

        if len(kwargs) == 0:
            self.reset()

    def reset(self):
        self.name = 'Unnamed Address'
        self.crypto = None
        self.address = None

    def as_obj(self):
        obj = {}

        if self.name is not None: obj['name'] = self.name
        if self.address is not None: obj['address'] = self.address
        if self.crypto is not None: obj['crypto'] = self.crypto

        return obj
