import asyncio
import logging
import re


class GPUControl:
    def __init__(self):
        self.controllers = {}

        self.load_gpu('nvidia')
        self.load_gpu('amd')

    def load_gpu(self, controller_id):
        controller = __import__('modules.client.gpu.%s' % controller_id, globals(), locals(), ['object'], 0)
        self.controllers[controller_id] = controller.__api__()

    async def setup(self):
        for controller_id, controller in self.controllers.items():
            await controller.setup()

    async def apply(self, hardware, overclock):
        for controller_id, controller in self.controllers.items():
            await controller.apply(hardware, overclock)

    async def revert(self, hardware):
        for controller_id, controller in self.controllers.items():
            await controller.revert(hardware)

    async def get_stats(self, hardware):
        gpu_stats = []

        for gpu in hardware.gpus:
            for controller_id, controller in self.controllers.items():
                if controller.is_mine(gpu):
                    gpu_stats.append(await controller.get_stats(gpu))

        return gpu_stats

class API:
    async def setup(self):
        pass

    def is_mine(self, gpu):
        pass

    async def apply(self, hardware, overclock):
        pass

    async def revert(self, hardware):
        pass

    async def get_stats(self, gpu):
        return {
            'temp': 0,
            'fan': 0
        }

    async def run_cmd(self, action, cmd):
        proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        logger = logging.getLogger(action)
        asyncio.ensure_future(self._read_stream(logger, proc.stdout, error=False))
        asyncio.ensure_future(self._read_stream(logger, proc.stderr, error=True))

        await proc.wait()

    async def _read_stream(self, logger, stream, error):
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
