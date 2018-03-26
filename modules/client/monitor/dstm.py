import socket
import json

from . import API


class DSTMAPI(API):
    async def get_stats(self, host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, 2222))
        s.send('\n'.encode("utf-8"))
        data = json.loads(s.recv(2048).decode("utf-8"))
        s.close()

        accepted = 0
        rejected = 0
        hashrate = []

        for entry in data['result']:
            accepted += entry['accepted_shares']
            rejected += entry['rejected_shares']
            hashrate.append(entry['sol_ps'])

        return {
            'shares': {
                'accepted': accepted,
                'invalid': 0,
                'rejected': rejected
            },
            'hashrate': hashrate
        }

__api__ = DSTMAPI
