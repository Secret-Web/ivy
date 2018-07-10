import asyncio

from ivy.module import Module
from ivy.net import NetConnector

from . import http_server
from .service import RelayService


class RelayModule(Module):
    IS_RELAY = True

    def on_load(self):
        self.service = RelayService(self, port=29203)
        self.ivy.register_service(self.service)

        asyncio.Task(http_server.start())

__plugin__ = RelayModule
