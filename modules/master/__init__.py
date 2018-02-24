import asyncio

from ivy.module import Module
from ivy.net import NetConnector

from . import http_server
from .service import MasterService


class MasterModule(Module):
    def on_load(self):
        self.service = MasterService(self, port=29203)
        self.ivy.register_service(self.service)

        asyncio.Task(http_server.start())

__plugin__ = MasterModule
