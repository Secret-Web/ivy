import asyncio

from ivy.module import Module
from ivy.net import NetConnector
from ivy.model.client import Client
from ivy.model.hardware import get_hardware

from . import api_server
from .gpu import GPUControl
from .monitor import Monitor
from .process import Process


class ClientModule(Module):
    def on_load(self):
        if 'worker_id' not in self.config:
            self.config['worker_id'] = self.ivy.id
        self.config['hardware'] = get_hardware()

        self.client = Client(**dict({'machine_id': self.ivy.id}, **self.config))

        self.connector = NetConnector(self.logger.getChild('socket'))
        self.connector.listen_event('connection', 'open')(self.event_connection_open)
        self.connector.listen_event('connection', 'closed')(self.event_connection_closed)

        self.register_events(self.connector)

        self.gpus = GPUControl()

        self.process = Process(self)
        self.monitor = Monitor(self)

        self.master_priority = None
        self.ivy.register_listener('master')(self.on_discovery_master)

        asyncio.ensure_future(api_server.start(self))

    def on_discovery_master(self, protocol, service):
        if self.master_priority is None or service.payload['priority'] < self.master_priority:
            self.logger.info('Connecting to primary %r...' % service)

            self.connector.open(service.ip, service.port, {
                'Miner-ID': self.ivy.id,
                'Subscribe': {
                    'machine': ['action'],
                    'fee': ['update']
                }
            })

            self.master_priority = service.payload['priority']

    async def event_connection_open(self, packet):
        await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

    async def event_connection_closed(self, packet):
        self.master_priority = None

    def register_events(self, l):
        @l.listen_event('machine', 'action')
        async def event(packet):
            self.logger.info('Action received: %r' % packet.payload)
            if packet.payload['id'] == 'upgrade':
                await self.ivy.upgrade_script(packet.payload['version'])
            elif packet.payload['id'] == 'patch':
                self.client.update(**packet.payload)

                self.config.update(self.client.as_obj())
                self.ivy.save_config()
            elif packet.payload['id'] == 'refresh':
                self.client.update(**packet.payload)

                await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

                self.config.update(self.client.as_obj())
                self.ivy.save_config()

                await self.process.start(self.client)

        @l.listen_event('fee', 'update')
        async def event(packet):
            self.client.fee = Fee(**packet.payload)

__plugin__ = ClientModule
