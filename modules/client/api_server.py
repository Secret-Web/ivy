import os
import json
import asyncio

from aiohttp import web


client = None

async def index(request):
    return web.Response(text=json.dumps(client.process.monitor.as_obj()), content_type='text/html')

app = web.Application()

app.router.add_get('/', index)

async def start(client_instance):
    global client
    client = client_instance

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 29205)
    await site.start()
