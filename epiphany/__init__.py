import logging
import asyncio
import socket

from .protocol import DiscoveryProtocol
from .service import Service


class Epiphany:
    def __init__(self, port, loop=asyncio.get_event_loop()):
        self.logger = logging.getLogger('Epiphany')

        self.port = port

        self.services = {}
        self.listeners = {'*': []}

        self.loop = loop
        self.listen_task = None
        self.protocol = None

    def on_discovery(self, protocol, services):
        for service in services:
            if service.id in self.listeners:
                for listener in self.listeners[service.id]:
                    listener(protocol, service)

            for listener in self.listeners['*']:
                listener(protocol, service)

    def register_service(self, service):
        self.logger.debug('Registering service: %r' % service.id)

        self.services[service.id] = service
        service.loop = self.loop
        service.start_service()

    def register_listener(self, arg):
        if callable(arg):
            self.logger.debug('Registered listener for \'*\': %r' % arg.__name__)

            self.listeners['*'].append(arg)
        else:
            arg = arg.upper()

            if arg not in self.listeners:
                self.listeners[arg] = []

            def inner(func):
                self.logger.debug('Registered listener for %r: %r' % (arg, func.__name__))

                self.listeners[arg].append(func)
                return func
            return inner

    def begin(self):
        self.start()
        self.discover()

    def start(self):
        self.logger.info('Initializing discovery...')

        if self.listen_task is not None: return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind(('', self.port))

        self.listen_task = self.loop.create_datagram_endpoint(DiscoveryProtocol, sock=self._sock)
        self.protocol = self.loop.run_until_complete(self.listen_task)[1]
        self.protocol.epiphany = self

    def discover(self):
        self.protocol.start_discovery()

    def run_forever(self):
        self.loop.run_forever()
