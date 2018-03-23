class AMDAPI:
    async def setup(self):
        pass

    async def is_mine(self, gpu):
        return 'AMD' in gpu.vendor

    async def apply(self, hardware, overclock):
        pass

    async def revert(self, hardware):
        pass

__api__ = AMDAPI
