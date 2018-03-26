import socket
import json
import aiohttp

from . import API


class ClaymoreAPI(API):
    async def get_stats(self, host):
        session = aiohttp.ClientSession()
        async with session.ws_connect('ws://127.0.0.1:4068/histo', protocols=('text',)) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.data)
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

        return {
            'shares': {
                'accepted': 0,
                'invalid': 0,
                'rejected': 0
            },
            'hashrate': 0
        }

__api__ = ClaymoreAPI
