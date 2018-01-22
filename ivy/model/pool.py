class Pool:
    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.name = kwargs['name'] if 'name' in kwargs else 'Unnamed Pool'
        self.endpoint = PoolEndpoint(**kwargs['endpoint']) if 'endpoint' in kwargs else None
        self.endpoints = {k: PoolEndpoint(**v) for k, v in kwargs['endpoints'].items()} if 'endpoints' in kwargs else {}

    def as_obj(self):
        obj = {}

        if self.name is not None: obj['name'] = self.name
        if self.endpoint is not None: obj['endpoint'] = self.endpoint.as_obj()
        if self.endpoints is not None: obj['endpoints'] = {k: v.as_obj() for k, v in self.endpoints.items()}

        return obj

class PoolEndpoint:
    def __init__(self, **kwargs):
        self.crypto = kwargs['crypto'] if 'crypto' in kwargs else None
        self.name = kwargs['name'] if 'name' in kwargs else None
        self.url = kwargs['url'] if 'url' in kwargs else None

        self.username = kwargs['username'] if 'username' in kwargs else None
        self.password = kwargs['password'] if 'password' in kwargs else None

        self.stratum = kwargs['stratum'] if 'stratum' in kwargs else False

    def as_obj(self):
        obj = {}

        if self.crypto is not None: obj['crypto'] = self.crypto
        if self.name is not None: obj['name'] = self.name
        if self.url is not None: obj['url'] = self.url

        if self.username is not None: obj['username'] = self.username
        if self.password is not None: obj['password'] = self.password

        if self.stratum is not None: obj['stratum'] = self.stratum

        return obj
