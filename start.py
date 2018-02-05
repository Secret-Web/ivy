import logging
import os
import asyncio, concurrent

from ivy import Ivy


class LastPartFilter(logging.Filter):
    def filter(self, record):
        record.name_last = record.name.rsplit('.', 1)[-1]
        return True

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
except:
    logger.critical('Shutting down...')
