import socket

from . import API


class ClaymoreAPI(API):
    async def get_stats(self, host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, 4068))
        s.send('histo\n'.encode("utf-8"))
        data = s.recv(2048).decode("utf-8")
        s.close()

        print(data)

        return {
            'shares': {
                'accepted': 0,
                'invalid': 0,
                'rejected': 0
            },
            'hashrate': 0
        }

__api__ = ClaymoreAPI
