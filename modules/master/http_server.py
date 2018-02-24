import os
import asyncio

from aiohttp import web


dist_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dist')

index_html = ''
with open(os.path.join(dist_folder, 'index.html'), 'r') as f:
    index_html = f.read().replace('\n', '')

async def index(request):
    return web.Response(text=index_html, content_type='text/html')

app = web.Application()

app.router.add_get('/', index)
app.router.add_static('/static/', path=os.path.join(dist_folder, 'static'), name='static')


async def start():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 80)
    await site.start()
