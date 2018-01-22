from datetime import datetime


class Message:
    def __init__(self, **kwargs):
        today = datetime.utcnow()
        datestr = '%d-%.2d-%.2d %.2d:%.2d:%d' % (today.year, today.month, today.day, today.hour, today.minute, today.second)
        self.time = datestr

        self.level = kwargs['level'] if 'level' in kwargs else None
        self.title = kwargs['title'] if 'title' in kwargs else None
        self.text = kwargs['text'] if 'text' in kwargs else None

        self.group = kwargs['group'] if 'group' in kwargs else None
        self.machine = kwargs['machine'] if 'machine' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.time is not None: obj['time'] = self.time

        if self.level is not None: obj['level'] = self.level
        if self.title is not None: obj['title'] = self.title
        if self.text is not None: obj['text'] = self.text

        if self.group is not None: obj['group'] = self.group
        if self.machine is not None: obj['machine'] = self.machine

        return obj
