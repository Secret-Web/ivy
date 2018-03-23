import asyncio
import logging
import re


class GPUControl:
    def __init__(self):
        self.gpus = {}

        self.load_gpu('nvidia')
        self.load_gpu('amd')

    def load_gpu(self, gpu_id):
        api = __import__('modules.client.gpu.%s' % gpu_id, globals(), locals(), ['object'], 0)
        self.gpus[gpu_id] = api.__api__()

    async def setup(self):
        for gpu_id, gpu in self.gpus.items():
            await gpu.setup()

    async def apply(self, hardware, overclock):
        for gpu_id, gpu in self.gpus.items():
            await gpu.apply(hardware, overclock)

    async def revert(self, hardware):
        for gpu_id, gpu in self.gpus.items():
            await gpu.revert(hardware)

class API:
    async def setup(self):
        pass

    async def apply(self, hardware, overclock):
        pass

    async def revert(self, hardware):
        pass

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
