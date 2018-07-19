import socket
import json

from . import API


class ClaymoreAPI(API):
    def get_forced_args(self):
        return '-wd 0'

    async def get_stats(self, host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, 3333))
        s.send('{"id": 0, "jsonrpc": "2.0", "method": "miner_getstat1"}'.encode("utf-8"))
        data = json.loads(s.recv(2048).decode("utf-8"))
        s.close()

        version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = data['result']

        runtime = int(runtime)

        eth_totals = [int(x) for x in eth_totals.split(';')]
        eth_hashrates = [float(x) * 1000 for x in eth_hashrates.split(';')]

        stats = stats.split(';')
        stats = [[273.15 + float(stats[i * 2]), int(stats[i * 2 + 1])] for i in range(int(len(stats) / 2))]

        invalids = [int(x) for x in invalids.split(';')]

        return {
            'shares': {
                'accepted': eth_totals[1],
                'invalid': invalids[0],
                'rejected': eth_totals[2]
            },
            'hashrate': eth_hashrates
        }

__api__ = ClaymoreAPI
