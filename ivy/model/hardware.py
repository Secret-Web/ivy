import shlex
import json
from subprocess import Popen, PIPE

import psutil

from ivy import get_mac


def get_stdout(cmd):
    args = shlex.split(cmd)

    proc = Popen(args, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()
    exitcode = proc.returncode

    return exitcode, out.decode('utf-8'), err

def get_hardware():
    # Get display devices, strip the newlines off the end
    out = get_stdout('lshw -json')[1]
    hardware = json.loads(out)

    cpus = []
    memory = []
    gpus = []

    for x in search_hw(hardware):
        if x['id'] == 'cpu':
            if 'vendor' not in x: continue

            cpus.append({
                'vendor': x['vendor'],
                'product': x['product'],
                'width': x['width'],
                'bus_id': x['businfo'],
                'cores': x['configuration']['cores'] if 'configuration' in x else None,
                'threads': x['configuration']['threads'] if 'configuration' in x else None
            })
        elif x['id'] == 'memory':
            if 'vendor' in x: continue
            memory.append({
                'size': x['size']
            })
        elif x['id'] == 'display':
            if 'vendor' not in x: continue

            gpus.append({
                'bus_id': x['businfo'],
                'vendor': x['vendor'],
                'product': x['product'],
                'width': x['width'],
                'clock': x['clock'],
                'driver': None #x['configuration']['driver']
            })

    storage = []

    for disk in psutil.disk_partitions():
        usage = psutil.disk_usage(disk.mountpoint)
        storage.append({
            'mount': disk.device,
            'fstype': disk.fstype,
            'space': {
                'free': usage.free,
                'used': usage.used,
                'total': usage.total
            }
        })

    return {
        'mac': get_mac(),
        'cpus': cpus,
        'memory': memory,
        'gpus': gpus,
        'storage': storage
    }

def search_hw(hardware):
    if 'children' not in hardware: return

    for child in hardware['children']:
        yield child
        for piece in search_hw(child):
            yield piece

class Hardware:
    def __init__(self, **kwargs):
        self.mac = kwargs['mac'] if 'mac' in kwargs else None
        self.cpus = [CPU(**data) for data in kwargs['cpus']] if 'cpus' in kwargs else None
        self.gpus = [GPU(**data) for data in kwargs['gpus']] if 'gpus' in kwargs else None
        self.memory = [Memory(**data) for data in kwargs['memory']] if 'memory' in kwargs else None

        self.storage = [Storage(**data) for data in kwargs['storage']] if 'storage' in kwargs else None

        self.overclock_nvidia = Overclock(**kwargs['overclock']['nvidia'] if 'overclock' in kwargs and 'nvidia' in kwargs['overclock'] else {})
        self.overclock_amd = Overclock(**kwargs['overclock']['amd'] if 'overclock' in kwargs and 'amd' in kwargs['overclock'] else {})

    def reset(self):
        self.overclock.reset()

    def as_obj(self):
        obj = {}

        if self.mac is not None: obj['mac'] = self.mac
        if self.cpus is not None: obj['cpus'] = [x.as_obj() for x in self.cpus]
        if self.gpus is not None: obj['gpus'] = [x.as_obj() for x in self.gpus]
        if self.memory is not None: obj['memory'] = [x.as_obj() for x in self.memory]

        if self.storage is not None: obj['storage'] = [x.as_obj() for x in self.storage]

        obj['overclock'] = {}
        if self.overclock_nvidia is not None: obj['overclock']['nvidia'] = self.overclock_nvidia.as_obj()
        if self.overclock_amd is not None: obj['overclock']['amd'] = self.overclock_amd.as_obj()

        return obj

class CPU:
    def __init__(self, **kwargs):
        self.bus_id = kwargs['bus_id'] if 'bus_id' in kwargs else None
        self.width = kwargs['width'] if 'width' in kwargs else None

        self.vendor = kwargs['vendor'] if 'vendor' in kwargs else None
        self.product = kwargs['product'] if 'product' in kwargs else None

        self.cores = kwargs['cores'] if 'cores' in kwargs else None
        self.threads = kwargs['threads'] if 'threads' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.bus_id is not None: obj['bus_id'] = self.bus_id
        if self.width is not None: obj['width'] = self.width

        if self.vendor is not None: obj['vendor'] = self.vendor
        if self.product is not None: obj['product'] = self.product

        if self.cores is not None: obj['cores'] = self.cores
        if self.threads is not None: obj['threads'] = self.threads

        return obj

class GPU:
    def __init__(self, **kwargs):
        self.bus_id = kwargs['bus_id'] if 'bus_id' in kwargs else None
        self.width = kwargs['width'] if 'width' in kwargs else None

        self.vendor = kwargs['vendor'] if 'vendor' in kwargs else None
        self.product = kwargs['product'] if 'product' in kwargs else None

        self.clock = kwargs['clock'] if 'clock' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.bus_id is not None: obj['bus_id'] = self.bus_id
        if self.width is not None: obj['width'] = self.width

        if self.vendor is not None: obj['vendor'] = self.vendor
        if self.product is not None: obj['product'] = self.product

        if self.clock is not None: obj['clock'] = self.clock

        return obj

class Memory:
    def __init__(self, **kwargs):
        self.size = kwargs['size'] if 'size' in kwargs else None

    def as_obj(self):
        obj = {}

        if self.size: obj['size'] = self.size

        return obj

class Storage:
    def __init__(self, **kwargs):
        self.mount = kwargs['mount'] if 'mount' in kwargs else None
        self.fstype = kwargs['fstype'] if 'fstype' in kwargs else None
        self.space = kwargs['space'] if 'space' in kwargs else {'free': 0, 'used': 0, 'total': 0}

    def as_obj(self):
        obj = {}

        if self.mount is not None: obj['mount'] = self.mount
        if self.fstype is not None: obj['fstype'] = self.fstype

        if self.space is not None: obj['space'] = self.space

        return obj

class Overclock:
    def __init__(self, **kwargs):
        self.core = kwargs['core'] if 'core' in kwargs else {'mhz': None, 'vlt': None}
        self.mem = kwargs['mem'] if 'mem' in kwargs else {'mhz': None, 'vlt': None}

        self.fan = kwargs['fan'] if 'fan' in kwargs else {'min': None}
        self.temp = kwargs['temp'] if 'temp' in kwargs else {'max': None}

        self.pwr = kwargs['pwr'] if 'pwr' in kwargs else None

    def reset(self):
        self.core = None
        self.mem = None

        self.fan = None
        self.temp = None

        self.pwr = None

    def as_obj(self):
        obj = {}

        if self.core is not None: obj['core'] = self.core
        if self.mem is not None: obj['mem'] = self.mem

        if self.fan is not None: obj['fan'] = self.fan
        if self.temp is not None: obj['temp'] = self.temp

        if self.pwr is not None: obj['pwr'] = self.pwr

        return obj
