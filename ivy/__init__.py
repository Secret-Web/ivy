import uuid
import random
import time
import string
import logging
import os
import json

from epiphany import Epiphany


def get_mac():
  mac_num = hex(uuid.getnode()).replace('0x', '').upper()
  mac = '-'.join(mac_num[i : i + 2] for i in range(0, 11, 2))
  return mac

def gen_id():
    random.seed(get_mac())
    id = ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(8))
    random.seed(time.time())
    return id

class Ivy:
    def __init__(self, config_file, epiphany_port=29204):
        self.logger = logging.getLogger('Ivy')

        self.id = gen_id()
        self.config_file = config_file
        self.config = {}

        self.epiphany = Epiphany(port=epiphany_port)

        self.modules = {}

        self.load_config()

        self.register_service = self.epiphany.register_service
        self.register_listener = self.epiphany.register_listener

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.save_config()

        with open(self.config_file, 'r') as f:
            self.config = json.load(f)

    def get_module(self, module_id):
        return self.modules[module_id]

    def add_module(self, module_id, config):
        self.logger.debug('Initializing module: %r' % module_id)

        mod = __import__('modules.%s' % module_id, globals(), locals(), ['object'], 0)

        self.modules[module_id] = mod.__plugin__(self, config=config, logger=self.logger.getChild(module_id))

    def start(self):
        for id, module in self.modules.items():
            self.logger.debug('Loading module: %r' % id)

            module.on_load()

        self.save_config()

        self.epiphany.begin()
