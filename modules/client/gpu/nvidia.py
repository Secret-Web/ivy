import socket
import json
from xml.dom import minidom

from . import API


class NvidiaAPI(API):
    async def setup(self):
        await self.run_cmd('IOC', 'nvidia-smi --persistence-mode=1 && nvidia-xconfig -a --allow-empty-initial-configuration --cool-bits=28 --enable-all-gpus')

    def is_mine(self, gpu):
        return 'NVIDIA' in gpu.vendor

    async def apply(self, hardware, overclock):
        nvidia = []

        for i, gpu in enumerate(hardware.gpus):
            if self.is_mine(gpu):
                for arg in self.apply_gpu(i, gpu, overclock.nvidia):
                    nvidia.append(arg)

        if len(nvidia) > 0:
            await self.run_cmd('SOC', '/usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(nvidia))

    def apply_gpu(self, i, gpu, overclock):
        if overclock.core['mhz']:
            yield '[gpu:%d]/GPUGraphicsClockOffset[3]=%d' % (i, overclock.core['mhz'])

        if overclock.mem['mhz']:
            yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=%d' % (i, overclock.mem['mhz'])

        if overclock.fan['min'] is not None:
            yield '[gpu:%d]/GPUFanControlState=1' % i
            yield '[fan:%d]/GPUTargetFanSpeed=%d' % (i, overclock.fan['min'])

    async def revert(self, hardware):
        nvidia = []

        for i, gpu in enumerate(hardware.gpus):
            if self.is_mine(gpu):
                for arg in NVIDIA.revert(i, gpu):
                    nvidia.append(arg)

        if len(nvidia) > 0:
            await self.run_cmd('ROC', '/usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(nvidia))

    def revert_gpu(self, i, gpu):
        yield '[gpu:%d]/GPUFanControlState=0' % i
        yield '[fan:%d]/GPUTargetFanSpeed=50' % i
        yield '[gpu:%d]/GPUGraphicsClockOffset[3]=0' % i
        yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=0' % i

    async def get_stats(self, gpu):
        stdout, stderr = await self.run_cmd('nvidia-smi -q -x')
        print(stdout)
        xmldoc = minidom.parseString(stdout)
        gpus = xmldoc.getElementsByTagName('gpu')
        print(gpu)
        print(len(gpus))
        for g in gpus:
            print(g.attributes['id'].value)

        return {
            'temp': 0,
            'fan': 10,
            'watts': 50
        }

__api__ = NvidiaAPI
