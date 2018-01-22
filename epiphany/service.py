class Service:
    def __init__(self, id, port):
        self._id = id.upper()
        self._port = port

    @property
    def id(self):
        return self._id

    @property
    def port(self):
        return self._port

    def start_service(self):
        pass

    def create_payload(self):
        pass

class ServiceResponse:
    def __init__(self, id, ip, port, payload={}):
        self.id = id
        self.ip = ip
        self.port = port
        self.payload = payload

    def __hash__(self):
        return hash((self.id, self.ip, self.port))

    def __eq__(self, cmp):
        return hash(self) == hash(cmp)

    def __repr__(self):
        return '%s <%s:%d>' % (self.id, self.ip, self.port)
