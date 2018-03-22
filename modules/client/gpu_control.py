import asyncio
import logging
import re

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
        if overclock.core['mhz']:
            yield '[gpu:%d]/GPUGraphicsClockOffset[3]=%d' % (i, overclock.core['mhz'])

        if overclock.mem['mhz']:
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

async def run_cmd(cmd):
    print(cmd)
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    logger = logging.getLogger('CMD')
    asyncio.ensure_future(_read_stream(logger, proc.stdout, error=False))
    asyncio.ensure_future(_read_stream(logger, proc.stderr, error=True))

    await proc.wait()

    logger.info('done')

async def _read_stream(logger, stream, error):
    while True:
        line = await stream.readline()
        if line:
            is_error = b'\033[0;31m' in line
            line = line.decode('UTF-8', errors='ignore').strip()
            line = re.sub('\033\[.+?m', '', line)

            if len(line) == 0: continue

            if is_error:
                logger.critical(line)
            elif error:
                logger.error(line)
            else:
                logger.info(line)
        else:
            break
