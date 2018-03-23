class AMDAPI:
    async def setup(self):
        pass

    async def apply(self, hardware, overclock):
        pass

    async def revert(self, hardware):
        pass

__api__ = AMDAPI
