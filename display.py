import asyncio
import subprocess
import logging
import os
import socket
import json
import traceback
import urllib.request

import urwid


IP = 'localhost'

palette = [
    ('gpus', '', '', '', '', '#333'),

    ('good', '', '', '', '', '#080'),
    ('bad', '', '', '', '', '#800'),
    ('bg-sidebar', '', '', '', '', '#000'),
    ('bg', '', '', '', '#fff', '#000'),]

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

        self.urwid = urwid.MainLoop(
            urwid.AttrMap(
                urwid.Columns([
                    urwid.LineBox(
                        self.output,
                        title='Output'
                    ), ('fixed', 48,
                        urwid.AttrMap(urwid.Filler(
                            urwid.Padding(
                                urwid.Pile([
                                    urwid.LineBox(urwid.Pile([
                                        self.name,
                                        self.wallet_crypto,

                                        urwid.Divider(),

                                        self.pool_name,
                                        self.pool_url,

                                        urwid.Divider(),

                                        self.wallet_name,
                                        self.wallet_address
                                    ])),

                                    urwid.Divider(),

                                    urwid.LineBox(urwid.Pile([
                                        urwid.AttrMap(self.accepted, 'good'),
                                        urwid.AttrMap(self.rejected, 'bad'),
                                        urwid.AttrMap(self.invalid, 'bad')
                                    ]), title='Shares'),

                                    urwid.Divider(),

                                    urwid.AttrMap(
                                        urwid.LineBox(urwid.Columns([
                                            self.gpus_names,
                                            self.gpus_temps,
                                            self.gpus_fans,
                                            self.gpus_rate
                                        ]), title='GPUs')
                                    , 'gpus')
                                ]), right=1, left=1
                            ), valign='top'
                    ), 'bg-sidebar'))
                ], focus_column=1)
            , 'bg'),
            palette,
            unhandled_input=self.on_key,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

        self.urwid.screen.set_terminal_properties(colors=256)

    def run(self):
        self.urwid.run()

    def on_key(self, key):
        if key == 'esc': raise urwid.ExitMainLoop()

    def get_pipe(self):
        return self.urwid.watch_pipe(lambda x: self.output.set_text(self.output.text + x.decode('utf8')))

loop = asyncio.get_event_loop()

display = Display(loop=loop)

async def update_stats():
    while True:
        try:
            data = json.loads(url_content('http://' + IP + ':29205'))

            display.name.set_text(data['config']['name'])

            display.wallet_name.set_text('Wallet: ' + data['config']['wallet']['name'])
            display.wallet_address.set_text(data['config']['wallet']['address'])
            display.wallet_crypto.set_text('- ' + data['config']['wallet']['crypto'] + ' -')

            display.pool_name.set_text('Pool: ' + data['config']['pool']['endpoint']['name'])
            display.pool_url.set_text(data['config']['pool']['endpoint']['url'])

            display.accepted.set_text('Accepted: %d shares' % data['shares']['accepted'])
            display.rejected.set_text('Rejected: %d shares' % data['shares']['rejected'])
            display.invalid.set_text('Invalid : %d shares' % data['shares']['rejected'])

            stats = data['hardware']['gpus']
            display.gpus_names.set_text('\n' + '\n'.join(['GPU%d' % i for i in range(len(stats))]))
            display.gpus_temps.set_text('Temp\n' + '\n'.join(['%dK' % stats[i]['temp'] for i in range(len(stats))]))
            display.gpus_fans.set_text('Fan\n' + '\n'.join(['%d%%' % stats[i]['fan'] for i in range(len(stats))]))
            display.gpus_rate.set_text('Rate\n' + '\n'.join(['%.2f/s' % (stats[i]['rate'] / 1000) for i in range(len(stats))]))

            if len(data['output']) > 0:
                display.output_lines.clear()
                for line in data['output']:
                    display.output_lines.append(urwid.Text(line))
                display.output_lines.set_focus(len(data['output']) - 1)
        except Exception as e:
            display.output_lines.append(urwid.Text(traceback.format_exc()))

        await asyncio.sleep(.5)

loop.create_task(update_stats())

display.run()

