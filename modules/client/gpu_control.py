import asyncio


async def run_cmd(cmd):
    print(cmd)
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.wait()

async def setup():
    await NVIDIA.apply()
    await AMD.apply()

async def apply(hardware, overclock):
    for i, gpu in enumerate(hardware.gpus):
        if 'NVIDIA' in gpu.vendor:
            await NVIDIA.apply(i, gpu, overclock.nvidia)
        elif 'AMD' in gpu.vendor:
            await AMD.apply(i, gpu, overclock.amd)
        else:
            print('Unknown GPU[%d] Vendor:' % i)
            print(gpu.as_obj())

async def revert(hardware):
    for i, gpu in enumerate(hardware.gpus):
        if 'NVIDIA' in gpu.vendor:
            await NVIDIA.revert(i, gpu)
        elif 'AMD' in gpu.vendor:
            await AMD.revert(i, gpu)
        else:
            print('Unknown GPU[%d] Vendor:' % i)
            print(gpu.as_obj())

class NVIDIA:
    async def setup():
        await run_cmd('nvidia-xconfig -a --allow-empty-initial-configuration --cool-bits=28 --enable-all-gpus')

    async def apply(i, gpu, overclock):
        applies = [
            '[gpu:%d]/GPUGraphicsClockOffset[3]=0' % i,
            '[gpu:%d]/GPUMemoryTransferRateOffset[3]=0' % i
        ]

        if overclock.fan['min'] is not None:
            applies.append('[gpu:%d]/GPUFanControlState=1' % i)
            applies.append('[fan:%d]/GPUTargetFanSpeed=%d' % (i, overclock.fan['min']))

        await run_cmd('xinit /usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(applies))

    async def revert(i, gpu):
        applies = [
            '[gpu:%d]/GPUFanControlState=0' % i,
            '[fan:%d]/GPUTargetFanSpeed=50' % i,
            '[gpu:%d]/GPUGraphicsClockOffset[3]=0' % i,
            '[gpu:%d]/GPUMemoryTransferRateOffset[3]=0' % i
        ]
        await run_cmd('xinit /usr/bin/nvidia-settings -c :0 -a "%s"' % '" -a "'.join(applies))

class AMD:
    async def apply(i, gpu):
        pass

    async def revert(i, gpu):
        pass
