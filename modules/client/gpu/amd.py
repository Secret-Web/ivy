from . import API


class AMDAPI(API):
    def is_mine(self, gpu):
        return 'AMD' in gpu.vendor

    async def setup(self, gpus):
        for i, gpu in gpus:
            await self.run_cmd('STP', 'sudo sh -c "echo manual > /sys/class/drm/card%d/device/power_dpm_force_performance_level"' % i)

    async def apply(self, gpus, overclock):
        for i, gpu in gpus:
            await self.apply_gpu(i, gpu, overclock.amd)

    async def apply_gpu(self, i, gpu, overclock):
        if overclock.pwr:
            await self.run_cmd('PWR', 'sudo /usr/bin/ohgodatool --set-max-power %d' % overclock.pwr)

        if overclock.core['mhz']:
            await self.run_cmd('CMZ', 'sudo /usr/bin/ohgodatool -i %d --core-state 0 --core-clock %d' % (i, overclock.core['mhz']))

        if overclock.core['vlt']:
            await self.run_cmd('CVT', 'sudo /usr/bin/ohgodatool -i %d --volt-state 0 --vddci %d' % (i, overclock.core['vlt']))

        if overclock.mem['mhz']:
            await self.run_cmd('MMZ', 'sudo /usr/bin/ohgodatool -i %d --mem-state 0 --mem-clock %d' % (i, overclock.mem['mhz']))

        if overclock.mem['vlt']:
            await self.run_cmd('MVT', 'sudo /usr/bin/ohgodatool -i %d --volt-state 0 --mvdd %d' % (i, overclock.mem['vlt']))

        if overclock.fan['min']:
            await self.run_cmd('FAN', 'sudo /usr/bin/ohgodatool -i %d --set-fanspeed %d' % (i, overclock.fan['min']))

    async def revert(self, hardware):
        # Not yet implemented.
        pass

    async def get_stats(self, i, gpu):
        temp = 0
        fan = [None, None]
        watts = 0

        with open('/sys/class/drm/card%d/device/hwmon/hwmon%d/temp1_input' % (i, i), 'r') as f:
            temp = (float(f.read()) / 1000.0) + 273.15
        
        with open('/sys/class/drm/card%d/device/hwmon/hwmon%d/pwm1' % (i, i), 'r') as f:
            fan[0] = float(f.read())
        
        with open('/sys/class/drm/card%d/device/hwmon/hwmon%d/pwm1_max' % (i, i), 'r') as f:
            fan[1] = float(f.read())
        
        with open('/sys/class/drm/card%d/device/hwmon/hwmon%d/power1_average' % (i, i), 'r') as f:
            watts = int(f.read()) / 1000000

        return {
            'temp': temp,
            'fan': int(((fan[0] / fan[1]) if fan[0] is not None and fan[1] is not None else 0) * 100),
            'watts': watts
        }

__api__ = AMDAPI
