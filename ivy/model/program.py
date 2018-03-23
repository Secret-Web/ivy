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

        return obj
