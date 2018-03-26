import os
import json
import re
from datetime import datetime, date, timedelta
import sqlite3


regex = re.compile(r'^(?:(?P<years>\d+?)yr)?(?:(?P<months>\d+?)mth)?(?:(?P<days>\d+?)d)?(?:(?P<hours>\d+?)hr)?(?:(?P<minutes>\d+?)m)?(?:(?P<seconds>\d+?)s)?$')
def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for (name, param) in parts.items():
        if param:
            time_params[name] = int(param)
    if 'months' in time_params:
        time_params['days'] = time_params['months'] * 30 + (time_params['days'] if 'days' in time_params else 0)
        del time_params['months']
    return timedelta(**time_params)

def ceil_dt(dt, delta):
    return dt + (datetime.min - dt) % delta

class Stats:
    def __init__(self):
        self._machines = {}

    def push(self, id, data):
        if id not in self._machines:
            self._machines[id] = new_pack()
        stats = self._machines[id]

        stats['snapshots'] += 1

        if 'online' in data and data['online']:
            stats['online'] += 1
        else:
            stats['offline'] += 1

        if 'shares' in data:
            stats['shares']['invalid'] += data['shares']['invalid']
            stats['shares']['accepted'] += data['shares']['accepted']
            stats['shares']['rejected'] += data['shares']['rejected']

        if 'hardware' in data:
            if 'gpus' in data['hardware']:
                for piece in data['hardware']['gpus']:
                    stats['gpus'] += 1
                    stats['rate'] += piece['rate']

    @property
    def machines(self):
        totals = {}

        for id, data in self._machines.items():
            total = new_pack()

            total['online'] += data['online'] / data['snapshots']
            total['offline'] += data['offline'] / data['snapshots']
            total['gpus'] += data['gpus'] / data['snapshots']
            total['rate'] += data['rate'] / data['snapshots']

            total['shares']['invalid'] += data['shares']['invalid']
            total['shares']['accepted'] += data['shares']['accepted']
            total['shares']['rejected'] += data['shares']['rejected']

            totals[id] = total

        return totals

    def result(self):
        total = new_pack()

        for id, data in self._machines.items():
            total['online'] += data['online'] / data['snapshots']
            total['offline'] += data['offline'] / data['snapshots']
            total['gpus'] += data['gpus'] / data['snapshots']
            total['rate'] += data['rate'] / data['snapshots']

            total['shares']['invalid'] += data['shares']['invalid']
            total['shares']['accepted'] += data['shares']['accepted']
            total['shares']['rejected'] += data['shares']['rejected']

        return total

def new_pack():
    return {
        'snapshots': 0,

        'gpus': 0,
        'online': 0,
        'offline': 0,
        'rate': 0,
        'shares': {
            'invalid': 0,
            'accepted': 0,
            'rejected': 0
        }
    }

class Store:
    def __init__(self):
        self.sql = sqlite3.connect(os.path.join(os.getcwd(), 'data', 'statistics.sql'))
        self.query = self.sql.cursor()

        self.query.execute('''
CREATE TABLE IF NOT EXISTS `snapshots` (
  `machine_id` VARCHAR(64) NOT NULL,
  `date` DATETIME NOT NULL,
  `snapshot` TEXT NOT NULL,
  PRIMARY KEY (`machine_id`, `date`)
)''')

        self.query.execute('''
CREATE TABLE IF NOT EXISTS `statistics` (
  `machine_id` VARCHAR(64) NOT NULL,
  `date` DATETIME NOT NULL,
  `gpus` INT(11) NOT NULL,
  `online` INT(11) NOT NULL,
  `offline` INT(11) NOT NULL,
  `rate` INT(11) NOT NULL,
  `shares_invalid` INT(11) NOT NULL,
  `shares_accepted` INT(11) NOT NULL,
  `shares_rejected` INT(11) NOT NULL,
  PRIMARY KEY (`machine_id`, `date`)
)''')

        self.sql.commit()

    def save(self, snapshots):
        today = datetime.utcnow()
        datestr = '%d-%.2d-%.2d %.2d:%.2d:%.2d' % (today.year, today.month, today.day, today.hour, today.minute, today.second)

        # Save the raw snapshot just in case we want to do additional stuff later.
        self.query.executemany('INSERT INTO `snapshots` VALUES(?, ?, ?)', [(id, datestr, json.dumps(data)) for id, data in snapshots.items()])

        stats = Stats()
        for id, data in snapshots.items():
            stats.push(id, data)

        datestr = '%d-%.2d-%.2d %.2d:%.2d:00' % (today.year, today.month, today.day, today.hour, today.minute)

        rows = []
        for id, total in stats.machines.items():
            rows.append(
                        (
                            id,
                            datestr,

                            total['gpus'],
                            total['online'],
                            total['offline'],
                            total['rate'],
                            total['shares']['invalid'],
                            total['shares']['accepted'],
                            total['shares']['rejected']
                        )
                    )

        self.query.executemany('''REPLACE INTO `statistics` VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)''', rows)

        self.sql.commit()

    def get_statistics(self, start, end, increment, machine=None):
        '''
            Start and end dates are in YYYY-MM-DD HH:MM:SS format.
            Increment: 0 = 5 minutes, 1 = 10 minutes, 2 = 30 minutes, 3 = 1 hour, 4 = 6 hours, 5 = 12 hours, 6 = 1 day, 7 = 1 week
        '''
        increment = parse_time(increment)

        end = ceil_dt(end, increment)

        if start is None:
            start = end - increment * 24

        results = []

        if end < start:
            return results

        time_stats = [start, None]
        machine_stats = None

        rows = self.query.execute('SELECT * FROM `snapshots` WHERE `date` BETWEEN ? and ?', (start, end))
        for row in rows:
            if machine is not None and row[0] is not machine:
                continue

            row_time = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')

            while machine_stats is None or row_time - time_stats[0] >= increment:
                if machine_stats is not None:
                    for id, data in machine_stats.items():
                        time_stats[1]['online'] += data['online'] / data['snapshots']
                        time_stats[1]['offline'] += data['offline'] / data['snapshots']
                        time_stats[1]['gpus'] += data['gpus'] / data['snapshots']
                        time_stats[1]['rate'] += data['rate'] / data['snapshots']

                        time_stats[1]['shares']['invalid'] += data['shares']['invalid']
                        time_stats[1]['shares']['accepted'] += data['shares']['accepted']
                        time_stats[1]['shares']['rejected'] += data['shares']['rejected']

                time_stats = [time_stats[0] + increment, None]
                machine_stats = {}
                results.append(time_stats)

            if time_stats[1] is None:
                time_stats[1] = new_pack()

            data = json.loads(row[2])

            if row[0] not in machine_stats:
                machine_stats[row[0]] = new_pack()
                machine_stats[row[0]]['snapshots'] = 0
            stat = machine_stats[row[0]]

            stat['snapshots'] += 1

            if 'online' in data and data['online']:
                stat['online'] += 1
            else:
                stat['offline'] += 1

            if 'shares' in data:
                stat['shares']['invalid'] += data['shares']['invalid']
                stat['shares']['accepted'] += data['shares']['accepted']
                stat['shares']['rejected'] += data['shares']['rejected']

            if 'hardware' in data:
                if 'gpus' in data['hardware']:
                    for piece in data['hardware']['gpus']:
                        stat['gpus'] += 1
                        stat['rate'] += piece['rate']

        while time_stats[0] < end:
            time_stats = [time_stats[0] + increment, None]
            results.append(time_stats)

        for row in results:
            row[0] = '%d-%.2d-%.2d %.2d:%.2d:%.2d' % (row[0].year, row[0].month, row[0].day, row[0].hour, row[0].minute, row[0].second)

        return results
