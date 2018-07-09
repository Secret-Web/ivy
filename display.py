import asyncio
import subprocess
import logging
import os
import socket
import json
import traceback
from urllib.error import URLError
import urllib.request

import urwid


IP = 'localhost'

palette = [
    ('background', '', '', '', '#FFF', '#000'),

    ('pool_header', '', '', '', '#0FF', '#000'),
    ('wallet_header', '', '', '', '#0FF', '#000'),

    ('shares_good', '', '', '', '#0F0', '#000'),
    ('shares_bad', '', '', '', '#F7E', '#000'),

    ('gpus_header', '', '', '', '#999', '#000'),
    ('gpus_item', '', '', '', '#FF0', '#000'),

    ('graph_bg', '', '', '', '', '#000'),
    ('graph_1', '', '', '', '', '#FF0'),
    ('graph_2', '', '', '', '', '#FF0')
]

def url_content(url):
    response = urllib.request.urlopen(urllib.request.Request(
        url,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    ))
    return response.read().decode('utf-8')

class Display:
    def __init__(self, loop):
        self.output_lines = urwid.SimpleListWalker([urwid.Text('Loading...')])
        self.output = urwid.ListBox(self.output_lines)

        self.name = urwid.Text('Loading data...', align='center')

        self.wallet_crypto = urwid.Text('Loading data...', align='center')
        self.wallet_name = urwid.Text('Loading data...', align='center')
        self.wallet_address = urwid.Text('Loading data...', align='center')

        self.pool_name = urwid.Text('Loading data...', align='center')
        self.pool_url = urwid.Text('Loading data...', align='center')

        self.accepted = urwid.Text('Loading data...')
        self.rejected = urwid.Text('Loading data...')
        self.invalid = urwid.Text('Loading data...')

        self.gpus_names = urwid.Text('Loading data...')
        self.gpus_temps = urwid.Text('Loading data...')
        self.gpus_fans = urwid.Text('Loading data...')
        self.gpus_rate = urwid.Text('Loading data...')

        self.hashrate = urwid.Text('Loading data...', align='center')
        self.hash_graph = urwid.BarGraph(['graph_bg', 'graph_1', 'graph_2'])
        self.hash_graph_length = 48 * 2
        self.hash_graph_data = []

        self.branding = urwid.Text('- SecretWeb.com -', align='center')

        self.urwid = urwid.MainLoop(
            urwid.AttrMap(urwid.Columns([
                urwid.LineBox(
                    self.output,
                    title='Output'
                ), ('fixed', 48,
                    urwid.Filler(
                        urwid.Padding(
                            urwid.Pile([
                                urwid.LineBox(urwid.Pile([
                                    self.name,
                                    self.wallet_crypto,

                                    urwid.Divider(),

                                    urwid.AttrMap(self.pool_name, 'pool_header'),
                                    self.pool_url,

                                    urwid.Divider(),

                                    urwid.AttrMap(self.wallet_name, 'wallet_header'),
                                    self.wallet_address
                                ])),

                                urwid.Divider(),

                                urwid.LineBox(urwid.Pile([
                                    urwid.AttrMap(self.accepted, 'shares_good'),
                                    urwid.AttrMap(self.rejected, 'shares_bad'),
                                    urwid.AttrMap(self.invalid, 'shares_bad')
                                ]), title='Shares'),

                                urwid.Divider(),

                                urwid.LineBox(urwid.Columns([
                                    urwid.AttrMap(self.gpus_names, 'gpus_header'),
                                    urwid.AttrMap(self.gpus_temps, 'gpus_item'),
                                    urwid.AttrMap(self.gpus_fans, 'gpus_item'),
                                    urwid.AttrMap(self.gpus_rate, 'gpus_item')
                                ]), title='GPUs'),

                                urwid.Divider(),

                                urwid.LineBox(urwid.Pile([
                                    self.hashrate,

                                    urwid.Divider(),

                                    urwid.BoxAdapter(self.hash_graph, height=15)
                                ]), title='Hashrate'),

                                urwid.Divider(),

                                self.branding
                            ]),
                        right=1, left=1),
                    valign='top')
                )
            ], focus_column=1), 'background'),
            palette,
            unhandled_input=self.on_key,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

        self.urwid.screen.set_terminal_properties(colors=256)

    def add_hash_data(self, value):
        if len(self.hash_graph_data) == 0 and value == 0: return

        self.hash_graph_data.append(value)

        del self.hash_graph_data[:-self.hash_graph_length]

        minrate = min(self.hash_graph_data)
        maxrate = max(self.hash_graph_data)

        if minrate == maxrate: minrate -= 1

        diff = maxrate - minrate

        data = []
        for value in self.hash_graph_data:
            data.append([0, value - minrate + diff])

        self.hash_graph.set_data(data, top=diff * 3)

    def run(self):
        self.urwid.run()

    def on_key(self, key):
        if key == 'esc': raise urwid.ExitMainLoop()

    def get_pipe(self):
        return self.urwid.watch_pipe(lambda x: self.output.set_text(self.output.text + x.decode('utf8')))

loop = asyncio.get_event_loop()

display = Display(loop=loop)

def convert_rate(rate):
    if rate > 10000000000000: return (rate / 1000000000000, 'G')
    elif rate > 10000000000: return (rate / 1000000000, 'G')
    elif rate > 10000000: return (rate / 1000000, 'M')
    elif rate > 10000: return (rate / 1000, 'k')
    return (rate, '')

async def update_stats():
    while True:
        try:
            data = json.loads(url_content('http://' + IP + ':29205'))

            if not data['online']:
                display.output_lines.append(urwid.Text('No program running. Is one configured or did it crash?'))

            if 'name' in data['config']:
                display.name.set_text(data['config']['name'])
            else:
                display.name.set_text('- N/A -')

            if 'wallet' in data['config']:
                display.wallet_name.set_text('Wallet: ' + data['config']['wallet']['name'])
                display.wallet_address.set_text(data['config']['wallet']['address'])
                display.wallet_crypto.set_text('- ' + data['config']['wallet']['crypto'] + ' -')
            else:
                display.wallet_name.set_text('Wallet: None')
                display.wallet_address.set_text('')
                display.wallet_crypto.set_text('- N/A -')

            if 'pool' in data['config']:
                display.pool_name.set_text('Pool: ' + data['config']['pool']['endpoint']['name'])
                display.pool_url.set_text(data['config']['pool']['endpoint']['url'])
            else:
                display.pool_name.set_text('Pool: None')
                display.pool_url.set_text('- N/A -')

            display.accepted.set_text('Accepted: %d shares' % data['shares']['accepted'])
            display.rejected.set_text('Rejected: %d shares' % data['shares']['rejected'])
            display.invalid.set_text('Invalid : %d shares' % data['shares']['invalid'])

            stats = data['hardware']['gpus']
            display.gpus_names.set_text('\n' + '\n'.join(['GPU%d' % i for i in range(len(stats))]))
            display.gpus_temps.set_text('Temp\n' + '\n'.join(['%d C' % (stats[i]['temp'] - 273.15) for i in range(len(stats))]))
            display.gpus_fans.set_text('Fan\n' + '\n'.join(['%d %%' % stats[i]['fan'] for i in range(len(stats))]))

            display.gpus_rate.set_text('Rate\n' + '\n'.join(['%.2f %s/s' % convert_rate(stats[i]['rate']) for i in range(len(stats))]))

            hashrate = sum([stats[i]['rate'] for i in range(len(stats))])
            display.hashrate.set_text('%.2f %s/s' % convert_rate(hashrate))
            display.add_hash_data(hashrate)

            if len(data['output']) > 0:
                display.output_lines.clear()
                for line in data['output']:
                    display.output_lines.append(urwid.Text(line))
        except URLError:
            display.output_lines.append(urwid.Text('Unable to establish a connection. Is Ivy online...?'))
        except Exception as e:
            display.output_lines.append(urwid.Text(traceback.format_exc()))

        display.output_lines.set_focus(len(display.output_lines) - 1)

        await asyncio.sleep(2)

loop.create_task(update_stats())

display.run()
