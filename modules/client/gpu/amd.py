from . import API


class AMDAPI(API):
    def is_mine(self, gpu):
        return 'AMD' in gpu.vendor

    async def setup(self, gpus):
        for i, gpu in gpus:
            await self.run_cmd('STP', 'sudo sh -c "echo manual > /sys/class/drm/card%d/device/power_dpm_force_performance_level"' % i)

    async def apply(self, hardware, overclock):
        for i, gpu in gpus:
            self.apply_gpu(i, gpu, overclock.amd)

    def apply_gpu(self, i, gpu, overclock):
        if overclock.pwr:
            await self.run_cmd('PWR', 'sudo /usr/bin/ohgodatool --set-max-power %d' % overclock.amd.pwr)

        if overclock.core['mhz']:
            await self.run_cmd('CMZ', 'sudo /usr/bin/ohgodatool -i %d --core-state 0 --core-clock %d' % (i, overclock.core['mhz'])

        if overclock.core['vlt']:
            await self.run_cmd('CVT', 'sudo /usr/bin/ohgodatool -i %d --volt-state 0 --vddci %d' % (i, overclock.core['vlt'])

        if overclock.mem['mhz']:
            await self.run_cmd('MMZ', 'sudo /usr/bin/ohgodatool -i %d --mem-state 0 --mem-clock %d' % (i, overclock.mem['mhz'])

        if overclock.mem['vlt']:
            await self.run_cmd('MVT', 'sudo /usr/bin/ohgodatool -i %d --volt-state 0 --mvdd %d' % (i, overclock.mem['vlt'])

        if overclock.fan['min']:
            await self.run_cmd('FAN', 'sudo /usr/bin/ohgodatool -i %d --set-fan-speed %d' % (i, overclock.fan['min']))

    async def revert(self, hardware):
        # Not yet implemented.
        pass

    async def get_stats(self, gpu):
        print('fetching stats for:', gpu.as_obj())

        return {
            'temp': 0,
            'fan': 0,
            'watts': 0
        }

__api__ = AMDAPI
