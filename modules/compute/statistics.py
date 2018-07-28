import os
import json
import re
from datetime import datetime, date, timedelta, timezone
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

def new_pack():
    return {
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

def compile_stats(interval_stats):
    stats = new_pack()

    for id, machine_stats in interval_stats.items():
        machine_stats['watts'] /= machine_stats['snapshots']
        machine_stats['temp'] /= machine_stats['snapshots']
        machine_stats['fan'] /= machine_stats['snapshots']
        machine_stats['rate'] /= machine_stats['snapshots']
    
        stats['watts'] += machine_stats['watts']

        if machine_stats['temp'] > stats['temp']:
            stats['temp'] = machine_stats['temp']

        if machine_stats['fan'] > stats['fan']:
            stats['fan'] = machine_stats['fan']

        stats['rate'] += machine_stats['rate']

        stats['shares']['accepted'] += machine_stats['shares']['accepted']
        stats['shares']['rejected'] += machine_stats['shares']['rejected']
        stats['shares']['invalid'] += machine_stats['shares']['invalid']

    return stats

class Store:
    def __init__(self, logger):
        self.logger = logger.getChild('stats')

        self.sql = sqlite3.connect(os.path.join('/etc', 'ivy', 'statistics.sql'))
        self.query = self.sql.cursor()

        self.logger.info('Creating table if it does not exist...')
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

    async def save_snapshot(self, snapshots):
        rows = []
        for id, stats in snapshots.items():
            print(stats.hardware.gpus)
            rows.append(
                        (
                            id,
                            stats.time,

                            stats.connected,
                            stats.status['type'],
                            stats.status['fee'],
                            
                            sum([gpu.watts for gpu in stats.hardware.gpus]),
                            max([gpu.temp for gpu in stats.hardware.gpus]),
                            max([gpu.fan for gpu in stats.hardware.gpus]),
                            sum([gpu.rate for gpu in stats.hardware.gpus]),

                            stats.shares['accepted'],
                            stats.shares['rejected'],
                            stats.shares['invalid']
                        )
                    )

        self.query.executemany('''REPLACE INTO `statistics` VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', rows)

        self.sql.commit()

    async def get_statistics(self, start=None, end=None, increment='5m', machine_id=None):
        if end is None:
            end = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()

        increment = parse_time(increment).total_seconds()

        end = end - end % increment

        if start is None:
            start = end - increment * 24

        results = []

        if end < start:
            return results

        interval_pack = [start, None]

        row = None
        if machine_id is None:
            rows = self.query.execute('SELECT * FROM `statistics` WHERE `date` BETWEEN ? and ?', (start, end + increment))
        else:
            rows = self.query.execute('SELECT * FROM `statistics` WHERE `machine_id` = ? AND `date` BETWEEN ? and ?', (machine_id, start, end + increment))

        interval_stats = None

        for row in rows:
            while row[1] - interval_pack[0] >= increment:
                if interval_stats is not None:
                    interval_pack[1] = compile_stats(interval_stats)

                    interval_stats = None

                interval_pack = [interval_pack[0] + increment, None]
                results.append(interval_pack)

            if interval_stats is None:
                interval_stats = {}
            
            if row[0] not in interval_stats:
                interval_stats[row[0]] = new_pack()
                interval_stats[row[0]]['snapshots'] = 0
            
            machine_stats = interval_stats[row[0]]
            
            machine_stats['snapshots'] += 1

            machine_stats['watts'] += row[5]
            machine_stats['temp'] += row[6]
            machine_stats['fan'] += row[7]
            machine_stats['rate'] += row[8]

            machine_stats['shares']['accepted'] += row[9]
            machine_stats['shares']['rejected'] += row[10]
            machine_stats['shares']['invalid'] += row[11]

        if interval_stats is not None:
            interval_pack[1] = compile_stats(interval_stats)

            interval_stats = None

        # Populate the `results` list with all increments remaining up to `end`
        while interval_pack[0] + increment <= end:
            interval_pack = [interval_pack[0] + increment, None]
            results.append(interval_pack)

        return results
