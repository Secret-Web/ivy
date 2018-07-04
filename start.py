import logging
import os
import sys
import asyncio, concurrent
import subprocess

from ivy import Ivy


class LastPartFilter(logging.Filter):
    def filter(self, record):
        record.name_last = record.name.rsplit('.', 1)[-1]
        return True

if not os.path.exists('data/config.json'):
    subprocess.call([sys.executable, 'install.py'])

if not os.path.exists('data/config.json'):
    exit()

s = Ivy(config_file='data/config.json')

for id, config in s.config.items():
    s.add_module(id, config)

try:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname).4s:%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M'))
    #handler.addFilter(LastPartFilter())

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    s.start()

    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    logger.critical('Shutting down...')
