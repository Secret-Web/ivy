import asyncio

from ivy.module import Module
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

        self.client = Client(**dict({'machine_id': self.ivy.id, 'hardware': get_hardware()}, **self.config))

        self.register_events(self.connector)

        self.gpus = GPUControl()

        self.process = Process(self)
        self.monitor = Monitor(self)

        asyncio.ensure_future(api_server.start(self))

    async def on_stop(self):
        await self.process.stop()

    def on_connect_relay(self, service):
        self.connector.open(service.ip, service.port, {
            'Miner-ID': self.ivy.id,
            'Subscribe': {
                'machine': ['action'],
                'fee': ['update']
            }
        })

    async def event_connection_open(self, packet):
        await super().event_connection_open(packet)

        self.monitor.stats.connected = True
        await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

    async def event_connection_closed(self, packet):
        await super().event_connection_closed(packet)

        self.monitor.stats.connected = False
        self.relay_priority = None

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

                await self.process.start()
            elif packet.payload['id'] == 'shutdown':
                os.system('/sbin/shutdown now')
            elif packet.payload['id'] == 'reboot':
                os.system('/sbin/shutdown -r now')

        @l.listen_event('fee', 'update')
        async def event(packet):
            self.client.program.fee.update(**packet.payload)

__plugin__ = ClientModule
