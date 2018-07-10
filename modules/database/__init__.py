import asyncio

from epyphany import Service
from ivy.module import Module

class StorageModule(Module):
    def on_load(self):
        if 'strategy' not in self.config:
            self.config['strategy'] = 'file'

        self.strategy = self.load_strategy(self.config['strategy'])

    def load_strategy(self, strategy_id):
        try:
            s = __import__('modules.storage.strategy.%s' % strategy_id, globals(), locals(), ['object'], 0)
            return s.__strategy__()
        except Exception as e:
            if strategy_id == 'file':
                return None

            self.logger.warning('Failed to load "%s" strategy. Falling back to "file".' % strategy_id)
            self.logger.exception('\n' + traceback.format_exc())
            return strategy_id('file')
    
    def on_connect_relay(self, service):
        pass

__plugin__ = StorageModule
