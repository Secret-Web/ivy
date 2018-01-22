from ivy.module import Module
from ivy.net import NetConnector

from .service import MasterService


class MasterModule(Module):
    def on_load(self):
        self.service = MasterService(self, port=29203)
        self.ivy.register_service(self.service)

__plugin__ = MasterModule
