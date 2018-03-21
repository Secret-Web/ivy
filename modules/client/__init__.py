import asyncio
import shlex
import json
import os
import time
import re
import socket
import traceback
import logging

import psutil

from ivy.module import Module
from ivy.net import NetConnector
from ivy.model.client import Client
from ivy.model.hardware import get_hardware
from ivy.model.stats import MinerStats

from . import api_server
from . import gpu_control
from .process import Process


class ClientModule(Module):
    def on_load(self):
        self.config['hardware'] = get_hardware()
        self.config['hardware']['storage'] = []

        for disk in psutil.disk_partitions():
            usage = psutil.disk_usage(disk.mountpoint)
            self.config['hardware']['storage'].append({
                'mount': disk.device,
                'fstype': disk.fstype,
                'space': {
                    'free': usage.free,
                    'used': usage.used,
                    'total': usage.total
                }
            })

        self.client = Client(**self.config)

        self.process = Process(self.logger, self.client)

        self.master_priority = None
        self.connector = NetConnector(self.logger.getChild('socket'))
        self.connector.listen_event('connection', 'open')(self.event_connection_open)
        self.connector.listen_event('connection', 'closed')(self.event_connection_closed)

        self.ivy.register_listener('master')(self.on_discovery_master)
        self.register_events(self.connector)

        asyncio.ensure_future(api_server.start(self))

    @property
    def uptime_path(self):
        return os.path.join('/tmp/.ivy-uptime')

    @property
    def miner_dir(self):
        cwd = os.path.join(os.getcwd(), 'data', 'miners')
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        return cwd

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

                await self.start_miner()

        @l.listen_event('fee', 'update')
        async def event(packet):
            self.client.fee = Fee(**packet.payload)

__plugin__ = ClientModule
