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

class Store:
    def __init__(self):
        self.sql = sqlite3.connect(os.path.join('/etc', 'ivy', 'statistics.sql'))
        self.query = self.sql.cursor()

        self.query.execute('''
CREATE TABLE IF NOT EXISTS `statistics` (
  `machine_id` VARCHAR(64) NOT NULL,
  `date` DATETIME NOT NULL,

  `connected` BOOLEAN NOT NULL,
  `status` INT(11) NOT NULL,
  `is_fee` BOOLEAN NOT NULL,

  `watts` INT(11) NOT NULL,
  `temp` INT(11) NOT NULL,
  `fan` INT(11) NOT NULL,
  `rate` INT(11) NOT NULL,

  `shares_accepted` INT(11) NOT NULL,
  `shares_rejected` INT(11) NOT NULL,
  `shares_invalid` INT(11) NOT NULL,
  PRIMARY KEY (`machine_id`, `date`)
)''')

        self.sql.commit()

    def save(self, snapshots):
        rows = []
        for id, stat in stats.machines.items():
            rows.append(
                        (
                            id,
                            stat.time,

                            stat.connected,
                            stat.status['type'],
                            stat.status['is_fee'],
                            
                            sum([gpu.watts for gpu in stat.hardware.gpus]),
                            max([gpu.temp for gpu in stat.hardware.gpus]),
                            max([gpu.fan for gpu in stat.hardware.gpus]),
                            sum([gpu.rate for gpu in stat.hardware.gpus]),

                            stat.shares['accepted'],
                            stat.shares['rejected'],
                            stat.shares['invalid']
                        )
                    )

        self.query.executemany('''REPLACE INTO `statistics` VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', rows)

        self.sql.commit()

    def get_statistics(self, start, end, increment, machine_id=None):
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

        row = None
        if machine_id is None:
            rows = self.query.execute('SELECT * FROM `statistics` WHERE `date` BETWEEN ? and ? AND `is_fee` = false', (start, end))
        else:
            rows = self.query.execute('SELECT * FROM `statistics` WHERE `date` BETWEEN ? and ? AND `is_fee` = false AND `machine_id` = ?', (start, end, machine_id))

        stats = None

        for row in rows:
            while row[1] - interval_stats[0] >= increment:
                if stats is not None:
                    stats['watts'] /= stats['snapshots']
                    stats['temp'] /= stats['snapshots']
                    stats['fan'] /= stats['snapshots']
                    stats['rate'] /= stats['snapshots']

                    interval_stats[1] = stats

                    stats = None

                interval_stats = [interval_stats[0] + increment, None]
                results.append(interval_stats)

            if stats is None:
                stats = {
                    'snapshots': 0,

                    'watts': 0,
                    'temp': 0,
                    'fan': 0,
                    'rate': 0,
                    
                    'shares': {
                        'accepted': 0,
                        'rejected': 0,
                        'invalid': 0
                    }
                }
            
            stats['snapshots'] += 1

            stats['watts'] += row[5]
            stats['temp'] += row[6]
            stats['fan'] += row[7]
            stats['rate'] += row[8]

            stats['shares']['accepted'] += row[9]
            stats['shares']['rejected'] += row[10]
            stats['shares']['invalid'] += row[11]

        # Populate the `results` list with all increments remaining up to `end`
        while interval_stats[0] < end:
            interval_stats = [interval_stats[0] + increment, None]
            results.append(interval_stats)

        return results
