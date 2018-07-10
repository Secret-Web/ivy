import asyncio

from epyphany import Service
from ivy.module import Module

class BackupModule(Module):
    def on_load(self):
        if 'schedules' not in self.config:
            self.config['schedules'] = []
    
    def on_connect_relay(self, service):
        pass

__plugin__ = BackupModule
