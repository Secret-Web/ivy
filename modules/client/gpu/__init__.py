import asyncio
import logging
import re


class GPUControl:
    def __init__(self):
        self.logger = logging.getLogger('GPU Controller')

        self.controllers = {}

        self.load_gpu('nvidia')
        self.load_gpu('amd')

    def load_gpu(self, controller_id):
        controller = __import__('modules.client.gpu.%s' % controller_id, globals(), locals(), ['object'], 0)
        self.controllers[controller_id] = controller.__api__()

    async def setup(self, hardware):
        for controller_id, controller in self.controllers.items():
            if controller.has_gpu(hardware):
                self.logger.info('Setting up %s GPUs' % controller_id.upper())
                await controller.setup([(i, gpu) for i, gpu in enumerate(hardware.gpus) if controller.is_mine(gpu)])

    async def apply(self, hardware, overclock):
        for controller_id, controller in self.controllers.items():
            if controller.has_gpu(hardware):
                self.logger.info('Applying overclock on %s GPUs' % controller_id.upper())
                data = overclock.as_obj()
                if controller_id in data:
                    self.logger.info(repr(data[controller_id]))
                await controller.apply([(i, gpu) for i, gpu in enumerate(hardware.gpus) if controller.is_mine(gpu)], overclock)

    async def revert(self, hardware):
        for controller_id, controller in self.controllers.items():
            if controller.has_gpu(hardware):
                self.logger.info('Reverting overclock on %s GPUs' % controller_id.upper())
                await controller.revert([(i, gpu) for i, gpu in enumerate(hardware.gpus) if controller.is_mine(gpu)])

    async def get_stats(self, hardware):
        gpu_stats = []

        for i, gpu in enumerate(hardware.gpus):
            for controller_id, controller in self.controllers.items():
                if controller.is_mine(gpu):
                    gpu_stats.append(await controller.get_stats(i, gpu))

        return gpu_stats

class API:
    def is_mine(self, gpu):
        pass

    def has_gpu(self, hardware):
        for i, gpu in enumerate(hardware.gpus):
            if self.is_mine(gpu):
                return True
        return False

    async def setup(self, hardware):
        pass

    async def apply(self, hardware, overclock):
        pass

    async def revert(self, hardware):
        pass

    async def get_stats(self, gpu):
        return {
            'temp': 0,
            'fan': 0,
            'watts': 0
        }

    async def run_cmd(self, action, cmd, quiet=False):
        proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        stdout, stderr = ([], [])

        logger = logging.getLogger(action)
        logger.info(cmd)

        asyncio.ensure_future(self._read_stream(logger, proc.stdout, stdout, quiet=quiet, error=False))
        asyncio.ensure_future(self._read_stream(logger, proc.stderr, stderr, quiet=quiet, error=True))

        await proc.wait()

        return (stdout, stderr)

    async def _read_stream(self, logger, stream, to, quiet, error):
        while True:
            line = await stream.readline()
            if line:
                is_error = b'\033[0;31m' in line
                line = line.decode('UTF-8', errors='ignore').strip()
                line = re.sub('\033\[.+?m', '', line)

                to.append(line)

                if not quiet:
                    if is_error:
                        logger.critical(line)
                    elif error:
                        logger.error(line)
                    else:
                        logger.info(line)
            else:
                break
