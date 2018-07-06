import uuid
import random
import time
import string
import logging
import os
import sys
import json
import asyncio

from epyphany import Epyphany


# This file is created when Ivy boots up, and is deleted when it gracefully shuts down.
# If this exists on start, some features will be disabled due to potential issues.
IVY_RUNNING_INDICATOR = os.path.join('/etc', 'ivy', '.ivy-running')

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
    def __init__(self, config_file, epyphany_port=29204):
        self.logger = logging.getLogger('Ivy')

        self.id = gen_id()
        self.config_file = config_file
        self.config = {}

        self.epyphany = Epyphany(port=epyphany_port)

        self.modules = {}

        self.load_config()

        self.register_service = self.epyphany.register_service
        self.register_listener = self.epyphany.register_listener

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
        self.is_safe = not os.path.exists(IVY_RUNNING_INDICATOR)

        open(IVY_RUNNING_INDICATOR, 'a').close()

        for id, module in self.modules.items():
            self.logger.debug('Loading module: %r' % id)

            module.on_load()

        self.save_config()

        self.epyphany.begin()
    
    def safe_shutdown(self):
        os.remove(IVY_RUNNING_INDICATOR)

    async def upgrade_script(self, version):
        self.logger.info('Upgrading script to commit %s...' % version['commit'])

        cmd = None

        updater = await asyncio.create_subprocess_exec(*['git', 'pull'], cwd=os.getcwd(),
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await updater.wait()

        updater = await asyncio.create_subprocess_exec(*['git', 'reset', '--hard', version['commit']], cwd=os.getcwd(),
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await updater.wait()

        asyncio.get_event_loop().stop()
