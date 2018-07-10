from ivy.net import NetConnector

class Module:
    def __init__(self, ivy, config={}, logger=None):
        self.ivy = ivy

        self.config = config
        self.logger = logger

        if not hasattr(self, 'IS_RELAY') or not self.IS_RELAY:
            self.relay_priority = None
            self.connector = NetConnector(self.logger.getChild('socket'))
            self.connector.listen_event('connection', 'open')(self.event_connection_open)
            self.connector.listen_event('connection', 'closed')(self.event_connection_closed)

            self.ivy.register_listener('relay')(self.on_discover_relay)

    def on_discover_relay(self, protocol, service):
        if self.relay_priority is None or service.payload['priority'] < self.relay_priority:
            self.relay_priority = service.payload['priority']

            self.logger.info('Connecting to primary %r...' % service)
            self.on_connect_relay(service)
    
    async def event_connection_open(self, packet):
        pass

    async def event_connection_closed(self, packet):
        if packet.dummy:
            self.relay_priority = None

    def on_connect_relay(self, service):
        pass

    def on_load(self):
        pass

    async def on_stop(self):
        pass
