from . import API


class AMDAPI(API):
    def is_mine(self, gpu):
        return 'AMD' in gpu.vendor

    async def setup(self, gpus):
        self.sclks = []
        self.mclks = []

        for i, gpu in gpus:
            await self.run_cmd('PWR', 'cat /sys/class/drm/card%d/device/pp_table > /tmp/pp_table.%d' % (i, i))

            with open('/sys/class/drm/card%d/device/pp_dpm_sclk' % i, 'r') as f:
                self.sclks.append(len(f.readlines()))
            with open('/sys/class/drm/card%d/device/pp_dpm_mclk' % i, 'r') as f:
                self.mclks.append(len(f.readlines()))

            await self.run_cmd('PWR', 'echo "performance" > /sys/class/drm/card%d/device/power_dpm_state' % i)
            await self.run_cmd('FPL', 'echo "high" > /sys/class/drm/card%d/device/power_dpm_force_performance_level' % i)

    async def apply(self, gpus, overclock):
        for i, gpu in gpus:
            await self.apply_gpu(i, gpu, overclock.amd)

    async def apply_gpu(self, i, gpu, overclock):
        async def ogat(tag, args):
            await self.run_cmd(tag, '/usr/bin/ohgodatool -i %d %s' % (i, args))

        if overclock.pwr:
            await ogat('OVC', '--set-max-power %d' % overclock.pwr)

        if overclock.core['mhz']:
            for j in range(0, self.sclks[i]):
                await ogat('SCC', '--core-state %d --core-clock %d' % (j, overclock.core['mhz']))

        if overclock.core['vlt']:
            for j in range(0, self.mclks[i]):
                await ogat('SCV', '--mem-state %d --vddci %d' % (j, overclock.core['vlt']))

        if overclock.mem['mhz']:
            for j in range(0, self.mclks[i]):
                await ogat('SMC', '--mem-state %d --mem-clock %d' % (j, overclock.mem['mhz']))

        if overclock.mem['vlt']:
            for j in range(0, self.mclks[i]):
                await ogat('SMV', '--mem-state %d --mvdd %d' % (j, overclock.mem['vlt']))

        if overclock.fan['min']:
            await ogat('SFS', '--set-fanspeed %d' % overclock.fan['min'])

    async def revert(self, gpus):
        for i, gpu in gpus:
            await self.run_cmd('PWR', 'cat /tmp/pp_table.%d > /sys/class/drm/card%d/device/pp_table' % (i, i))

            await self.run_cmd('PWR', 'echo 2 > /sys/class/drm/card%d/device/hwmon/hwmon%d/pwm1_enable' % (i, i))
            await self.run_cmd('FPL', 'echo "auto" > /sys/class/drm/card%d/device/power_dpm_force_performance_level' % i)

    async def get_stats(self, i, gpu):
        temp = 0
        fan = [None, None]
        watts = 0

        try:
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
        except:
            return {
                'temp': 0,
                'fan': 0,
                'watts': 0
            }

__api__ = AMDAPI
