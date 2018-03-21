import asyncio
import json
import time
import copy
import random
import string
import traceback
import os
import re

from epyphany import Service
from ivy.net import NetListener


# This value defines the maximum amount of machines allowed before
# stat updating on listeners happens in bulk. This helps prevent
# network lag on large farms.
IMMEDIATE_STAT_CUTOFF = 1000

class MasterService(Service):
    def __init__(self, module, port):
        super(MasterService, self).__init__('master', port)

        self.module = module
        self.listener = NetListener(module.logger.getChild('socket'))

        self.register_events(self.listener)

        # id: {socket, subscriptions: {event: [method, method, method]}}
        self.connections = {}

        # sub: {method: [id, id, id]}
        self.subscriptions = {}

    def start_service(self):
        self.module.logger.info('Starting master service...')

        self.listener.serve('', self.port)

    def create_payload(self):
        return {'id': self.module.ivy.id, 'priority': self.module.config['priority'] if 'priority' in self.module.config else 0}

    def register_events(self, l):
        @l.listen_event
        async def event(packet):
            one = False

            if packet.to:
                if packet.to == 'one':
                    one = True
                else:
                    if packet.to in self.connections:
                        await self.connections[packet.to]['socket'].send(packet.event, packet.method, payload=packet.payload, sender=packet.socket.id)
                    return

            # Miner events are a special case. They're sent in bulk if the number
            # of total machines exceeds 1000.
            #if packet.event == 'machine':
            #    return

            if packet.event in self.subscriptions:
                if packet.method in self.subscriptions[packet.event]:
                    for id in self.subscriptions[packet.event][packet.method]:
                        if id == packet.socket.id: continue

                        await self.connections[id]['socket'].send(packet.event, packet.method, payload=packet.payload, sender=packet.socket.id)

                        if one: return
                if '*' in self.subscriptions[packet.event]:
                    for id in self.subscriptions[packet.event]['*']:
                        if id == packet.socket.id: continue

                        await self.connections[id]['socket'].send(packet.event, packet.method, payload=packet.payload, sender=packet.socket.id)

                        if one: return

            if '*' in self.subscriptions:
                if packet.method in self.subscriptions['*']:
                    for id in self.subscriptions['*'][packet.method]:
                        if id == packet.socket.id: continue

                        await self.connections[id]['socket'].send(packet.event, packet.method, payload=packet.payload, sender=packet.socket.id)

                        if one: return
                if '*' in self.subscriptions['*']:
                    for id in self.subscriptions['*']['*']:
                        if id == packet.socket.id: continue

                        await self.connections[id]['socket'].send(packet.event, packet.method, payload=packet.payload, sender=packet.socket.id)

                        if one: return

        @l.listen_event('connection', 'open')
        async def event(packet):
            if 'Miner-ID' in packet.payload['headers']:
                packet.socket.id = packet.payload['headers']['Miner-ID']

            self.connections[packet.socket.id] = {'socket': packet.socket, 'subscriptions': {}}

            subscribe = None

            if len(packet.payload['path']) > 1:
                for _, key, value in re.findall('(\?|\&)([^=]+)\=([^&]+)', packet.payload['path']):
                    if key == 'subscribe':
                        subscribe = value

            if subscribe is None and 'Subscribe' in packet.payload['headers']:
                subscribe = packet.payload['headers']['Subscribe']

            if subscribe is not None:
                subscribe = subscribe.replace('\'', '"')
                try:
                    self.connections[packet.socket.id]['subscriptions'] = json.loads(subscribe)
                except:
                    self.module.logger.warning('Failed to load Subscribe: %s' % subscribe)

            for event, methods in self.connections[packet.socket.id]['subscriptions'].items():
                if event not in self.subscriptions: self.subscriptions[event] = {}
                for method in methods:
                    if method not in self.subscriptions[event]: self.subscriptions[event][method] = []
                    self.subscriptions[event][method].append(packet.socket.id)

        @l.listen_event('connection', 'closed')
        async def event(packet):
            for event, methods in self.connections[packet.socket.id]['subscriptions'].items():
                for method in methods:
                    self.subscriptions[event][method].remove(packet.socket.id)
            del self.connections[packet.socket.id]
