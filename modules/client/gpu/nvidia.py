import socket
import json
from xml.etree import ElementTree

from . import API


class NvidiaAPI(API):
    def is_mine(self, gpu):
        return 'NVIDIA' in gpu.vendor

    async def setup(self, gpus):
        await self.run_cmd('IOC', 'nvidia-smi --persistence-mode=1 && nvidia-xconfig -a --allow-empty-initial-configuration --cool-bits=28 --enable-all-gpus')

    async def apply(self, gpus, overclock):
        nvidia = []

        for i, gpu in gpus:
            for arg in self.apply_gpu(i, gpu, overclock.nvidia):
                nvidia.append(arg)

        if overclock.nvidia.pwr:
            await self.run_cmd('PWR', '/usr/bin/nvidia-smi --power-limit=%d' % overclock.nvidia.pwr)

        if len(nvidia) > 0:
            await self.run_cmd('SOC', '/usr/bin/nvidia-settings -c :99 -a "%s"' % '" -a "'.join(nvidia))

    def apply_gpu(self, i, gpu, overclock):
        yield '[gpu:%d]/GPUPowerMizerMode=1' % i

        if overclock.core['mhz']:
            yield '[gpu:%d]/GPUGraphicsClockOffset[3]=%d' % (i, overclock.core['mhz'])

        if overclock.mem['mhz']:
            yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=%d' % (i, overclock.mem['mhz'])

        if overclock.fan['min'] is not None:
            yield '[gpu:%d]/GPUFanControlState=1' % i
            yield '[fan:%d]/GPUTargetFanSpeed=%d' % (i, overclock.fan['min'])

    async def revert(self, gpus):
        nvidia = []

        for i, gpu in gpus:
            for arg in self.revert_gpu(i, gpu):
                nvidia.append(arg)

        await self.run_cmd('PWR', '/usr/bin/nvidia-smi --power-limit=320')

        if len(nvidia) > 0:
            await self.run_cmd('ROC', '/usr/bin/nvidia-settings -c :99 -a "%s"' % '" -a "'.join(nvidia))

    def revert_gpu(self, i, gpu):
        yield '[gpu:%d]/GPUFanControlState=0' % i
        yield '[fan:%d]/GPUTargetFanSpeed=50' % i
        yield '[gpu:%d]/GPUGraphicsClockOffset[3]=0' % i
        yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=0' % i

    async def get_stats(self, i, gpu):
        stdout, stderr = await self.run_cmd('stats', 'nvidia-smi -q -x', quiet=True)

        try:
            root = ElementTree.fromstring('\n'.join(stdout))
            for g in root.findall('gpu'):
                # Strip off "pci@"
                if gpu.bus_id[4:] == g.get('id')[4:]:
                    return {
                        'fan': float(g.find('fan_speed').text.split(' ')[0]),
                        'temp': int(g.find('temperature').find('gpu_temp').text.split(' ')[0]) + 273.15,
                        'watts': float(g.find('power_readings').find('power_draw').text.split(' ')[0])
                    }
        except:
            pass

        return {
            'temp': 0,
            'fan': 0,
            'watts': 0
        }

__api__ = NvidiaAPI
