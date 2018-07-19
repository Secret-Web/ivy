class API:
    def get_forced_args(self):
        return ''

    async def get_stats(self, host):
        return {
            'shares': {
                'accepted': 0,
                'invalid': 0,
                'rejected': 0
            },
            'hashrate': []
        }
