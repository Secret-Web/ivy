import os
import json
from datetime import datetime, date, timedelta
import sqlite3


def new_query_result():
    return {
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
    def query(self, start, end, increment):
        pass

    def statistics(self, data):
        pass

class FileStore(Store):
    def __init__(self):
        self.sql = sqlite3.connect(os.path.join(os.getcwd(), 'data', 'statistics.sql'))
        self.query = self.sql.cursor()

        self.query.execute('''
CREATE TABLE IF NOT EXISTS `statistics` (
  `machine_id` VARCHAR(64) NOT NULL,
  `date` DATETIME NOT NULL,
  `snapshot` TEXT NOT NULL,
  PRIMARY KEY (`machine_id`, `date`)
)''')
        self.sql.commit()

    def save(self, snapshot):
        today = datetime.utcnow()
        datestr = '%d-%.2d-%.2d %.2d:%.2d:%d' % (today.year, today.month, today.day, today.hour, today.minute, today.second)

        rows = []
        for id, data in snapshot.items():
            rows.append((id, datestr, json.dumps(data)))

        self.query.executemany('INSERT INTO `statistics` VALUES(?, ?, ?)', rows)
        self.sql.commit()

# ('tgik523Y', '2018-01-08 14:54:00', '{"invalid": 0, "runtime": 0, "online": false, "hardware": {"gpus": [{"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}, {"rate": 0, "fan": 63, "watts": 0, "online": true, "temp": 0}]}}')
    def statistics(self, start, end, increment=0, machine=None):
        '''
            Start and end dates are in YYYY-MM-DD HH:MM:SS format.
            Increment: 0 = 5 minutes, 1 = 10 minutes, 2 = 30 minutes, 3 = 1 hour, 4 = 6 hours, 5 = 12 hours, 6 = 1 day, 7 = 1 week
        '''
        delta = None

        now = datetime.utcnow()
        now -= timedelta(microseconds=now.microsecond)
        now -= timedelta(seconds=now.second)

        if increment == 0:
            if start is None:
                start = now - timedelta(hours=2)
            delta = timedelta(minutes=5)
            now -= timedelta(minutes=now.minute % 5)
        elif increment == 1:
            if start is None:
                start = now - timedelta(hours=6)
            delta = timedelta(minutes=10)
            now -= timedelta(minutes=now.minute % 10)
        elif increment == 2:
            if start is None:
                start = now - timedelta(hours=12)
            delta = timedelta(minutes=30)
            now -= timedelta(minutes=now.minute % 30)
        elif increment == 3:
            if start is None:
                start = now - timedelta(days=1)
            delta = timedelta(hours=1)
            now -= timedelta(minutes=now.minute)
        elif increment == 4:
            if start is None:
                start = now - timedelta(days=3)
            delta = timedelta(hours=6)
            now -= timedelta(hours=now.hour % 6, minutes=now.minute)
        elif increment == 5:
            if start is None:
                start = now - timedelta(weeks=1)
            delta = timedelta(hours=12)
            now -= timedelta(hours=now.hour % 12, minutes=now.minute)
        elif increment == 6:
            if start is None:
                start = now - timedelta(days=30)
            delta = timedelta(days=1)
            now -= timedelta(hours=now.hour, minutes=now.minute)
        elif increment == 7:
            if start is None:
                start = now - timedelta(days=365)
            delta = timedelta(days=7)
            now -= timedelta(days=now.day % 7, hours=now.hour, minutes=now.minute)
        else:
            return []

        results = []

        time_stats = None
        machine_stats = {}

        rows = self.query.execute('SELECT * FROM `statistics` WHERE `date` BETWEEN ? and ?', (start, end))
        for row in rows:
            if machine is not None and row[0] is not machine:
                continue

            row_time = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
            row_time += timedelta(seconds=60 - row_time.second)
            if increment == 0:
                row_time += timedelta(minutes=5 - row_time.minute % 5)
            elif increment == 1:
                row_time += timedelta(minutes=10 - row_time.minute % 10)
            elif increment == 2:
                row_time += timedelta(minutes=30 - row_time.minute % 30)
            elif increment == 3:
                row_time += timedelta(minutes=60 - row_time.minute)
            elif increment == 4:
                row_time += timedelta(hours=6 - row_time.hour % 6, minutes=60 - row_time.minute)
            elif increment == 5:
                row_time += timedelta(hours=12 - row_time.hour % 12, minutes=60 - row_time.minute)
            elif increment == 6:
                row_time += timedelta(hours=14 - row_time.hour, minutes=60 - row_time.minute)
            elif increment == 7:
                row_time += timedelta(days=7 - row_time.day % 7, hours=24 - row_time.hour, minutes=60 - row_time.minute)

            # Make a new column if
            if time_stats is not None:
                while row_time - time_stats[0] > delta:
                    if machine_stats is not None:
                        for id, data in machine_stats.items():
                            time_stats[1]['online'] += data['online'] / data['snapshots']
                            time_stats[1]['offline'] += data['offline'] / data['snapshots']
                            time_stats[1]['gpus'] += data['gpus'] / data['snapshots']
                            time_stats[1]['rate'] += data['rate'] / data['snapshots']

                    time_stats = [time_stats[0] + delta, None]
                    machine_stats = {}
                    results.append(time_stats)
            else:
                time_stats = [row_time, None]
                results.append(time_stats)

            if time_stats[1] is None:
                time_stats[1] = new_query_result()

            data = json.loads(row[2])

            if row[0] not in machine_stats:
                machine_stats[row[0]] = new_query_result()
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

        for row in results:
            row[0] = '%d-%.2d-%.2d %.2d:%.2d:00' % (row[0].year, row[0].month, row[0].day, row[0].hour, row[0].minute)

        return results
