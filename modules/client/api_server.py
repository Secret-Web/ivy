import os
import json
import asyncio

from aiohttp import web


client = None

async def index(request):
    return web.Response(text=json.dumps({
        'config': client.process.config.as_obj() if client.process.process.config is not None else {},
        'hardware': client.monitor.stats.hardware.as_obj(),
        'shares': client.monitor.shares,
        'output': client.monitor.output
    }), content_type='text/html')

app = web.Application()

app.router.add_get('/', index)

async def start(client_instance):
    global client
    client = client_instance

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 29205)
    await site.start()
