import os
import json
import time
import asyncio
import traceback
import urllib.request

from ivy.model.fee import Fee
from .statistics import Store


def url_content(url):
    response = urllib.request.urlopen(urllib.request.Request(
        url,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    ))
    return response.read().decode('utf-8')

class Database(dict):
    def __init__(self, ivy, logger, connector, config):
        self.ivy = ivy
        self.logger = logger.getChild('db')
        self.connector = connector
        self.config = config

        if 'last_check' not in self.config:
            self.config['last_check'] = 0

        self.statistics = Store()

        self.strategy = None
        asyncio.ensure_future(self.apply_strategy(config['type']))

        self.fee = Fee()
        self.stats = {}

        self.software = {}
        self.coins = {}
        self.tickers = {}
        self.fee_configs = {}

        self.software_file = os.path.join('/etc', 'ivy', 'software.json')
        if os.path.exists(self.software_file):
            try:
                with open(self.software_file, 'r') as f:
                    self.software = json.load(f)
            except:
                pass

        self.coins_file = os.path.join('/etc', 'ivy', 'coins.json')
        if os.path.exists(self.coins_file):
            try:
                with open(self.coins_file, 'r') as f:
                    self.coins = json.load(f)
            except:
                pass

        self.tickers_file = os.path.join('/etc', 'ivy', 'tickers.json')
        if os.path.exists(self.tickers_file):
            try:
                with open(self.tickers_file, 'r') as f:
                    self.tickers = json.load(f)
            except:
                pass

        self.fee_file = os.path.join('/etc', 'ivy', 'fee.json')
        if os.path.exists(self.fee_file):
            try:
                with open(self.fee_file, 'r') as f:
                    self.fee_configs = json.load(f)
            except:
                pass

        asyncio.ensure_future(self.update())

    def load_strategy(self, strategy_id):
        try:
            s = __import__('modules.compute.strategy.%s' % strategy_id, globals(), locals(), ['object'], 0)
            return s.__strategy__
        except Exception as e:
            if strategy_id == 'file':
                self.logger.exception('\n' + traceback.format_exc())
                return None

            self.logger.warning('Failed to load "%s" strategy. Falling back to "file".' % strategy_id)
            self.logger.exception('\n' + traceback.format_exc())
            return strategy_id('file')
    
    async def apply_strategy(self, strategy_id):
        if self.strategy is not None:
            await self.strategy.on_unbind(self.connector)

        self.strategy = self.load_strategy(strategy_id)(self.ivy, self.logger)

        await self.strategy.on_load(self.config)

        for thing in ['messages', 'pools', 'wallets', 'groups', 'machines']:
            if not hasattr(self.strategy, thing):
                raise Exception('Strategy does not implement a "%s" field.' % thing)

            setattr(self, thing, getattr(self.strategy, thing))
        
        await self.strategy.on_bind(self.connector)

        # Load default pools and insert if needed.
        if await self.strategy.pools.size() == 0:
            try:
                pools = json.loads(url_content('https://gist.githubusercontent.com/Stumblinbear/39d5643a45029ba99d8a410e6c110cd1/raw/pools.json'))
                for id, pool in pools.items():
                    await self.strategy.pools.put(id, pool)
            except Exception:
                self.logger.exception('\n' + traceback.format_exc())

    async def update(self):
        last_update = 0

        while True:
            try:
                coins1 = json.loads(url_content('https://whattomine.com/coins.json'))['coins']
                coins2 = json.loads(url_content('https://www.coincalculators.io/api/allcoins.aspx?hashrate=1'))

                self.coins.clear()

                for name, coin in coins1.items():
                    if 'Nicehash' in name: continue

                    self.coins[coin['tag']] = {
                        'name': name,
                        'algorithm': coin['algorithm'],
                        'block_time': coin['block_time'],
                        'block_reward': coin['block_reward'],
                        'nethash': coin['nethash'],
                        'exchange_rate': coin['exchange_rate']
                    }

                for coin in coins2:
                    if 'Nicehash' in coin['name']: continue

                    # Trust WhatToMine over CoinCalculators
                    if coin['symbol'] in self.coins: continue

                    self.coins[coin['symbol']] = {
                        'name': coin['name'],
                        'algorithm': coin['algorithm'],
                        'block_time': coin['blockTime'],
                        'block_reward': coin['blockReward'],
                        'nethash': coin['currentNethash'],
                        'exchange_rate': coin['price_btc']
                    }

                with open(self.coins_file, 'w') as f:
                    json.dump(self.coins, f, indent=2)
            except Exception:
                self.logger.exception('\n' + traceback.format_exc())

            try:
                self.tickers = json.loads(url_content('https://blockchain.info/ticker'))
                with open(self.tickers_file, 'w') as f:
                    json.dump(self.tickers, f, indent=2)
            except Exception:
                self.logger.exception('\n' + traceback.format_exc())

            try:
                self.fee_configs = json.loads(url_content('https://gist.githubusercontent.com/Stumblinbear/49958098740c453c11d62924dd20dc83/raw/fee.json'))
                with open(self.fee_file, 'w') as f:
                    json.dump(self.fee_configs, f, indent=2)
            except Exception:
                self.logger.exception('\n' + traceback.format_exc())

            # Update this shit once a day, bby
            if time.time() - self.config['last_check'] > 60 * 60 * 24 \
                or len(self.software) == 0:
                self.config['last_check'] = time.time()

                self.ivy.save_config()

                try:
                    self.software = json.loads(url_content('https://gist.githubusercontent.com/Stumblinbear/3a2f996c524412c03b12c3f38d87096e/raw/software.json'))
                    with open(self.software_file, 'w') as f:
                        json.dump(self.software, f, indent=2)
                except Exception:
                    self.logger.exception('\n' + traceback.format_exc())

            await asyncio.sleep(60 * 60)

    async def save_snapshot(self, snapshot):
        try:
            await self.strategy.save_snapshot(snapshot)
        except Exception as e:
            self.logger.exception('\n' + traceback.format_exc())
    
    async def get_statistics(self, *args, **kwargs):
        return await self.statistics.get_statistics(*args, **kwargs)
