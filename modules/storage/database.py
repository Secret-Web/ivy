import os
import json
import time
import asyncio
import traceback
import urllib.request

from ivy.model.fee import Fee
from ivy.model.message import Message
from ivy.model.pool import Pool
from ivy.model.wallet import Wallet
from ivy.model.group import Group
from ivy.model.client import Client


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
    def __init__(self, logger):
        self.logger = logger

        self.software = {}
        self.coins = {}
        self.tickers = {}

        self.software_file = os.path.join(os.getcwd(), 'data', 'software.json')
        if os.path.exists(self.software_file):
            try:
                with open(self.software_file, 'r') as f:
                    self.software = json.load(f)
            except:
                pass

        self.coins_file = os.path.join(os.getcwd(), 'data', 'coins.json')
        if os.path.exists(self.coins_file):
            try:
                with open(self.coins_file, 'r') as f:
                    self.coins = json.load(f)
            except:
                pass

        self.tickers_file = os.path.join(os.getcwd(), 'data', 'tickers.json')
        if os.path.exists(self.tickers_file):
            try:
                with open(self.tickers_file, 'r') as f:
                    self.tickers = json.load(f)
            except:
                pass

        self.fee_configs = {
            'ETH': {
                'pool': {
                    'config': {
                        'url': 'eth-us-east1.nanopool.org:9999',
                        'username': '0x691448966A3197f6eB6C1Aa424F960691b97b873',
                        'password': 'x',
                        'stratum': True
                    }
                },
                'program': {
                    'id': 'claymore-eth-v10.2',
                    'name': 'Claymore ETH v10.2',
                    'exec': {
                      'file': 'ethdcrminer64',
                      'args': '-epool {pool.url} -ewal {user} -epsw {pool.pass} -eworker {miner.id}'
                    },
                    'install': {
                      'url': 'https://drive.google.com/uc?export=download&id=1t25SK0lk2osr32GH623rR8aG2_qvZds9',
                      'strip_components': 1,
                      'exec': []
                    }
                }
            }
        }

        loaded = {}
        if os.path.exists(self.database_file):
            with open(self.database_file, 'r') as f:
                try:
                    loaded = json.load(f)
                except:
                    self.logger.error('Failed to decode database file! Trying backup...')
                    with open(self.database_file_backup, 'r') as ff:
                        try:
                            loaded = json.load(ff)
                        except:
                            self.logger.error('Failed to decode database file backup! Settings destroyed! Sorry!')

        if 'pools' not in loaded or len(loaded['pools']) == 0:
            try:
                loaded['pools'] = json.loads(url_content('https://gist.githubusercontent.com/Stumblinbear/39d5643a45029ba99d8a410e6c110cd1/raw/361d18e12d94200068a79b96c8936620ae366217/pools.json'))
            except Exception:
                self.logger.exception('\n' + traceback.format_exc())

        self.last_check = loaded['last_check'] if 'last_check' in loaded else 0
        self.fee = Fee(**loaded['fee'] if 'fee' in loaded else {})
        self.messages = [Message(**x) for x in loaded['messages']] if 'messages' in loaded else []
        self.pools = {k: Pool(**v) for k, v in loaded['pools'].items()} if 'pools' in loaded else {}
        self.wallets = {k: Wallet(**v) for k, v in loaded['wallets'].items()} if 'wallets' in loaded else {}
        self.groups = {k: Group(**v) for k, v in loaded['groups'].items()} if 'groups' in loaded else {}
        self.machines = {k: Client(**v) for k, v in loaded['machines'].items()} if 'machines' in loaded else {}

        self.stats = {}

        self.task = asyncio.ensure_future(self.periodic_save())

    @property
    def database_file(self):
        return os.path.join(os.getcwd(), 'data', 'database.json')

    @property
    def database_file_backup(self):
        return os.path.join(os.getcwd(), 'data', 'database.bak.json')

    def save(self):
        obj = {}

        obj['last_check'] = self.last_check
        obj['fee'] = self.fee.as_obj()
        obj['messages'] = [x.as_obj() for x in self.messages]
        obj['pools'] = {k: v.as_obj() for k, v in self.pools.items()}
        obj['wallets'] = {k: v.as_obj() for k, v in self.wallets.items()}
        obj['groups'] = {k: v.as_obj() for k, v in self.groups.items()}
        obj['machines'] = {k: v.as_obj() for k, v in self.machines.items()}

        if os.path.exists(self.database_file_backup):
            os.remove(self.database_file_backup)

        if os.path.exists(self.database_file):
            os.rename(self.database_file, self.database_file_backup)

        with open(self.database_file, 'w') as f:
            f.write(json.dumps(obj, indent=2))

    async def periodic_save(self):
        last_update = 0

        while True:
            # Wait 5 seconds between each save
            await asyncio.sleep(5)

            self.save()

            if time.time() - last_update > 60 * 60:
                self.update_data()

            # Update this shit once a day, bby
            if time.time() - self.last_check > 60 * 60 * 24 \
                or len(self.software) == 0:
                self.last_check = time.time()

                try:
                    self.software = json.loads(url_content('https://gist.githubusercontent.com/Stumblinbear/3a2f996c524412c03b12c3f38d87096e/raw/software.json'))
                    with open(self.software_file, 'w') as f:
                        json.dump(self.software, f, indent=2)
                except Exception:
                    self.logger.exception('\n' + traceback.format_exc())

    def update_data(self):
        try:
            coins = json.loads(url_content('https://whattomine.com/coins.json'))['coins']

            self.coins.clear()

            for name, coin in coins.items():
                coin['name'] = name
                self.coins[coin['tag']] = coin
                del coin['tag']

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
