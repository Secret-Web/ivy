templates = {
    'pool': lambda: {'name': 'Unset', 'configs': {}},
    'pool_config': lambda: {'crypto': None, 'name': 'Unset', 'url': None, 'user': None, 'pass': None},
    'wallet': lambda: {'crypto': None, 'name': None, 'address': None},
    'group': lambda: {
        'name': 'Unnamed',
        'pool': {'id': None, 'config': None},
        'program': {'exec': None},
        'hardware': {
            'overclock': {
                'core': {'mhz': None, 'vlt': None},
                'mem': {'mhz': None, 'vlt': None},
                'pwr': None,
                'fan': {'min': None},
                'temp': {'max': None}
            }
        }
    }
}
