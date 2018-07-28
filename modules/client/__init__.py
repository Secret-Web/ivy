import os
import asyncio

from ivy.module import Module
from ivy.model.client import Client
from ivy.model.hardware import get_hardware

from . import api_server
from .gpu import GPUControl
from .monitor import Monitor


class ClientModule(Module):
    def on_load(self):
        if 'worker_id' not in self.config:
            self.config['worker_id'] = self.ivy.id

        self.client = Client(**{**self.config, **{'machine_id': self.ivy.id, 'hardware': get_hardware()}})

        self.register_events(self.connector)

        self.message_queue = asyncio.Queue()
        asyncio.ensure_future(self.process_messages())

        self.gpus = GPUControl()

        self.monitor = Monitor(self)

        asyncio.ensure_future(api_server.start(self))

    async def on_stop(self):
        await self.monitor.on_stop()

    async def process_messages(self):
        while True:
            if not self.connector.socket:
                await asyncio.sleep(1)
                continue

            message = await self.message_queue.get()
            message['machine'] = self.client.machine_id

            await self.connector.socket.send('messages', 'new', message)

    def new_message(self, level=None, title=None, text=None):
        if level is None: raise Exception('Level not specified!')
        if text is None: raise Exception('Text not specified!')

        self.logger.info('[' + level.upper() + '] ' + ((title + ': ') if title else '') + text)

        pack = {'level': level, 'text': text}
        if title: pack['title'] = title
        self.message_queue.put_nowait(pack)

    def report_exception(self, e):
        self.new_message(level='bug', title='Miner Exception', text=str(e))

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

                self.config.update(**self.client.as_obj(slim=True))

                self.ivy.save_config()
            elif packet.payload['id'] == 'refresh':
                del packet.payload['id']

                self.client.update(**packet.payload)

                self.config.update(**self.client.as_obj(slim=True))

                self.ivy.save_config()

                await packet.send('machines', 'update', {self.ivy.id: self.client.as_obj()})

                await self.monitor.refresh_miner(self.client)
            elif packet.payload['id'] == 'shutdown':
                os.system('/sbin/shutdown now')
            elif packet.payload['id'] == 'reboot':
                os.system('/sbin/shutdown -r now')

        @l.listen_event('fee', 'update')
        async def event(packet):
            self.client.program.fee.update(**packet.payload)

__plugin__ = ClientModule
