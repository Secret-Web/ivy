import os
import json
import asyncio

from aiohttp import web


module = None

async def index(request):
    stats = module.monitor.stats.as_obj()
    stats.update({
        'config': module.process.config.as_obj() if module.process.config is not None else {},
        'output': module.monitor.output
    })

    return web.Response(text=json.dumps(stats), content_type='text/html')

app = web.Application()

app.router.add_get('/', index)

async def start(module_instance):
    global module
    module = module_instance

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 29205)
    await site.start()
