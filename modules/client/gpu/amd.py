from . import API


class AMDAPI(API):
    def is_mine(self, gpu):
        return 'AMD' in gpu.vendor

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

__api__ = AMDAPI
