import json
import asyncio

from .service import Service, ServiceResponse

'''
# Discovery Broadcast
{
    'services': ['text']
}
'''

class DiscoveryProtocol:
    def start_discovery(self):
        if hasattr(self, 'task') and self.task is not None:
            self.task.cancel()
        self.task = asyncio.Task(self.discovery_tick())

    async def discovery_tick(self):
        while True:
            services = []
            for id, service in self.epiphany.services.items():
                data = {'id': id, 'port': service.port, 'payload': service.create_payload()}
                if data['payload'] is not False:
                    services.append(data)
            self.broadcast({'services': services})
            await asyncio.sleep(1)

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = json.loads(data.decode())

        if 'services' in message:
            services = []
            for data in message['services']:
                data['ip'] = addr[0]
                service = ServiceResponse(**data)
                services.append(service)
            self.epiphany.on_discovery(self, services)

    def broadcast(self, data):
        self.transport.sendto(json.dumps(data).encode('UTF-8'), ('<broadcast>', self.epiphany.port))

    def send(self, addr, data):
        self.transport.sendto(json.dumps(data).encode('UTF-8'), addr)
