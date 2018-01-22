import asyncio
import subprocess
import logging
import os
import socket
import json
import traceback

import urwid


IP = '192.168.1.90'

class Display:
    def __init__(self, loop):
        self.output = urwid.Text('')

        self.pool = urwid.Text('Loading data...')

        self.accepted = urwid.Text('Loading data...')
        self.rejected = urwid.Text('Loading data...')
        self.invalid = urwid.Text('Loading data...')

        self.gpus_names = urwid.Text('Loading data...')
        self.gpus_temps = urwid.Text('Loading data...')
        self.gpus_fans = urwid.Text('Loading data...')

        self.urwid = urwid.MainLoop(
            urwid.Columns([
                urwid.LineBox(
                    urwid.Filler(self.output, valign='bottom'),
                    title='Output'
                ), ('fixed', 40, urwid.LineBox(
                    urwid.Filler(
                        urwid.Padding(
                            urwid.Pile([
                                self.pool,

                                urwid.Divider(),

                                self.accepted,
                                self.rejected,
                                self.invalid,

                                urwid.Divider(),

                                urwid.Columns([
                                    self.gpus_names,
                                    self.gpus_temps,
                                    self.gpus_fans
                                ])
                            ]), right=1, left=1
                        ), valign='top'
                    ),
                    title='System'
                ))
            ], focus_column=1),
            unhandled_input=self.on_key,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

    def run(self):
        self.urwid.run()

    def on_key(self, key):
        if key == 'esc': raise urwid.ExitMainLoop()

    def get_pipe(self):
        return self.urwid.watch_pipe(lambda x: self.output.set_text(self.output.text + x.decode('utf8')))

loop = asyncio.get_event_loop()

display = Display(loop=loop)

def get_stats():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((IP, 3333))
    s.send('{"id": 0, "jsonrpc": "2.0", "method": "miner_getstat1"}'.encode("utf-8"))
    data = json.loads(s.recv(2048).decode("utf-8"))
    s.close()

    version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = data['result']

    runtime = int(runtime)

    eth_totals = [int(x) for x in eth_totals.split(';')]
    eth_hashrates = [int(x) for x in eth_hashrates.split(';')]

    stats = stats.split(';')
    stats = [[273.15 + float(stats[i * 2]), int(stats[i * 2 + 1])] for i in range(int(len(stats) / 2))]

    invalids = [int(x) for x in invalids.split(';')]

    return version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids

async def update_stats():
    while True:
        try:
            version, runtime, eth_totals, eth_hashrates, dcr_totals, dcr_hashrates, stats, pools, invalids = get_stats()

            display.pool.set_text(pools)

            display.accepted.set_text('Accepted: %d shares' % eth_totals[1])
            display.rejected.set_text('Rejected: %d shares' % eth_totals[2])
            display.invalid.set_text('Invalid : %d shares' % invalids[0])

            display.gpus_names.set_text('\n' + '\n'.join(['GPU%d' % i for i in range(len(stats))]))
            display.gpus_temps.set_text('Temp\n' + '\n'.join(['%dK' % stats[i][0] for i in range(len(stats))]))
            display.gpus_fans.set_text('Fan\n' + '\n'.join(['%d%%' % stats[i][1] for i in range(len(stats))]))
        except Exception as e:
            display.output.set_text(display.output.text + traceback.format_exc())

        await asyncio.sleep(5)

loop.create_task(update_stats())

display.run()
#loop.run_forever()
