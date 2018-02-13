import json
import asyncio
import traceback
import urllib.parse

import websockets
from websockets.exceptions import ConnectionClosed


class SocketWrapper:
    def __init__(self, ws):
        self.id = ws.__hash__()
        self.ws = ws

    def open(self):
        return self.ws.open

    async def recv(self):
        return json.loads(await self.ws.recv())

    def close(self):
        self.ws.close()

    async def send(self, event, method, payload=None, to=None, sender=None):
        packet = {'event': event, 'method': method}

        if sender: packet['from'] = sender
        if to: packet['to'] = to
        if payload: packet['payload'] = payload

        await self.ws.send(json.dumps(packet))

class Packet:
    def __init__(self, socket, event, method, payload=None, to=None, **kwargs):
        self.dummy = kwargs['dummy'] if 'dummy' in kwargs else False

        self.socket = socket

        self.sender = kwargs['from'] if 'from' in kwargs else None

        self.event = event
        self.method = method

        self.to = to
        self.payload = payload

    async def send(self, *args, **kwargs):
        await self.socket.send(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        await self.socket.send(*args, **kwargs, to=self.sender)

    def __repr__(self):
        return str({
            'event': self.event,
            'method': self.method,
            'to': self.to,
            'payload': self.payload
        })

class Net:
    def __init__(self, logger):
        self.logger = logger

        self.events = {}

        self.task = None

    def listen_event(self, listen, method=None):
        if method is None: method = '*'

        if callable(listen):
            return self.listen_event('*', method)(listen)
        else:
            if listen not in self.events: self.events[listen] = {}
            if method not in self.events[listen]: self.events[listen][method] = []

        def inner(func):
            self.events[listen][method].append(func)
            return func
        return inner

    async def call_event(self, packet):
        if packet.event in self.events:
            if packet.method in self.events[packet.event]:
                for listener in self.events[packet.event][packet.method]:
                    try:
                        await listener(packet)
                    except:
                        self.logger.exception(traceback.format_exc())

            if '*' in self.events[packet.event]:
                for listener in self.events[packet.event]['*']:
                    try:
                        await listener(packet)
                    except:
                        self.logger.exception(traceback.format_exc())

        if '*' in self.events:
            if packet.method in self.events['*']:
                for listener in self.events['*'][packet.method]:
                    try:
                        await listener(packet)
                    except:
                        self.logger.exception(traceback.format_exc())

            if '*' in self.events['*']:
                for listener in self.events['*']['*']:
                    try:
                        await listener(packet)
                    except:
                        self.logger.exception(traceback.format_exc())

class NetListener(Net):
    def __init__(self, logger):
        super(NetListener, self).__init__(logger)

        self.connections = {}

    def serve(self, host, port):
        self.task = asyncio.ensure_future(websockets.serve(self.listener, host, port))

    async def listener(self, ws, path):
        socket = SocketWrapper(ws)

        headers = {k: v for k, v in ws.request_headers.items()}

        await self.call_event(Packet(socket, 'connection', 'open', payload={'headers': headers, 'path': urllib.parse.unquote(path)}, dummy=True))

        try:
            while True:
                data = await socket.recv()

                if 'event' in data and 'method' in data:
                    packet = Packet(socket, **data)
                    packet.sender = socket.id
                    await self.call_event(packet)
                else:
                    self.logger.warning('Unknown data received: %r' % data)
        except ConnectionClosed as e:
            if e.code != 1001 and e.code != 1006:
                self.logger.exception(traceback.format_exc())
        except Exception as e:
            self.logger.critical('Socket connection closed!')
            self.logger.exception('\n' + traceback.format_exc())
        finally:
            await self.call_event(Packet(socket, 'connection', 'closed', payload={'headers': headers, 'path': urllib.parse.unquote(path)}, dummy=True))

class NetConnector(Net):
    def __init__(self, logger):
        super(NetConnector, self).__init__(logger)

        self.socket = None

    def open(self, host, port, extra_headers=None):
        self.task = asyncio.ensure_future(self.listener(host, port, extra_headers=extra_headers))

    async def close(self):
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task

    async def listener(self, host, port, extra_headers=None):
        try:
            uri = 'ws://%s:%d/' % (host, port)

            self.logger.debug('Connecting to %s...' % uri)

            try:
                async with websockets.connect(uri, extra_headers=extra_headers) as ws:
                    self.socket = SocketWrapper(ws)

                    await self.call_event(Packet(self.socket, 'connection', 'open', dummy=True))

                    while True:
                        data = await self.socket.recv()

                        if 'event' in data and 'method' in data:
                            await self.call_event(Packet(self.socket, **data))
                        else:
                            self.logger.warning('Unknown data received: %r' % data)
            except ConnectionClosed as e:
                if e.code != 1001 and e.code != 1006:
                    raise e
                self.logger.warning('Master server closed.')
            except Exception as e:
                self.logger.critical('Connection closed! %r' % e)
        finally:
            await self.call_event(Packet(self.socket, 'connection', 'closed', dummy=True))
