class Fee:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.daily = kwargs['daily'] if 'daily' in kwargs else 15
        self.interval = kwargs['interval'] if 'interval' in kwargs else 4

    def as_obj(self):
        obj = {}

        if self.daily is not None: obj['daily'] = self.daily
        if self.interval is not None: obj['interval'] = self.interval

        return obj
