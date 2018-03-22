import asyncio


async def run_cmd(cmd):
    print(cmd)
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.wait()

async def setup():
    await NVIDIA.setup()
    await AMD.setup()

async def apply(hardware, overclock):
    nvidia = []
    amd = []

    for i, gpu in enumerate(hardware.gpus):
        if 'NVIDIA' in gpu.vendor:
            for arg in NVIDIA.apply(i, gpu, overclock.nvidia):
                nvidia.append(arg)
        elif 'AMD' in gpu.vendor:
            amd.append(*AMD.apply(i, gpu, overclock.amd))
        else:
            print('Unknown GPU[%d] Vendor:' % i)
            print(gpu.as_obj())

    if len(nvidia) > 0:
        await run_cmd('/usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(nvidia))

async def revert(hardware):
    nvidia = []
    amd = []

    for i, gpu in enumerate(hardware.gpus):
        if 'NVIDIA' in gpu.vendor:
            for arg in NVIDIA.revert(i, gpu):
                nvidia.append(arg)
        elif 'AMD' in gpu.vendor:
            amd.append(*AMD.revert(i, gpu))
        else:
            print('Unknown GPU[%d] Vendor:' % i)
            print(gpu.as_obj())

    if len(nvidia) > 0:
        await run_cmd('/usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(nvidia))

class NVIDIA:
    async def setup():
        await run_cmd('nvidia-smi --persistence-mode=1 && nvidia-xconfig -a --allow-empty-initial-configuration --cool-bits=28 --enable-all-gpus')

    def apply(i, gpu, overclock):
        yield '[gpu:%d]/GPUGraphicsClockOffset[3]=%d' % (i, overclock.core['mhz'])
        yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=%d' % (i, overclock.mem['mhz'])

        if overclock.fan['min'] is not None:
            yield '[gpu:%d]/GPUFanControlState=1' % i
            yield '[fan:%d]/GPUTargetFanSpeed=%d' % (i, overclock.fan['min'])

    def revert(i, gpu):
        yield '[gpu:%d]/GPUFanControlState=0' % i
        yield '[fan:%d]/GPUTargetFanSpeed=50' % i
        yield '[gpu:%d]/GPUGraphicsClockOffset[3]=0' % i
        yield '[gpu:%d]/GPUMemoryTransferRateOffset[3]=0' % i

class AMD:
    async def setup():
        pass

    def apply(i, gpu):
        pass

    def revert(i, gpu):
        pass
