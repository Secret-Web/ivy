import sys
import os
import json


class _Getch:
    """Gets a single character from standard input.  Does not echo to the
screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()


class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

_getch = _Getch()
def getch(accepted=None):
    char = None
    while True:
        char = _getch()
        if ord(char) == 3:
            print()
            sys.exit()
        char = char.lower()
        if accepted is None or char in accepted:
            break
    print(char)
    return char

class colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def yn(text, end=colors.ENDC):
    print(colors.YELLOW + text + ' [y/N] ', end=end, flush=True)
    ret = getch(['y', 'n']) == 'y'
    print('')
    return ret

os.system('cls' if os.name == 'nt' else 'clear')

print(colors.HEADER + colors.BOLD + '''
===========================![ Ivy Monitoring ]!=============================''')
print(colors.ENDC +
'''
Welcome to the ivy Monitor installer!  In the following few steps, I'll walk
you through  setting up your server.  If you have any  questions,  feel free  to
check our FAQ, or open up a support ticket on our website.
''')

is_farm = yn('Do you (or will you) have more than one machine running a mining script?')

if not is_farm:
    accepted = yn('''Alright. This server will run the mining script,  host the dashboard,  and store
statistical data. Is that what you want?''')
    if not accepted:
        is_farm = True

if not is_farm:
    is_client = is_relay = is_storage = True
else:
    is_client = yn('Will this machine be running a mining script?')

    is_relay = yn('''Will this  machine run the  dashboard  (or host a fallback of it)?  This is also
known as a RELAY SERVER;  it handles all communications  between storage devices
and your mining rigs.''')
    is_storage = yn('''Will this machine be storing farm data? This is also known as a STORAGE  SERVICE
because it does exactly that. It stores  the dashboard's  persistent data.  More
often than not, this  will be on your  RELAY  SERVER.  Some people may want some
additional data-security, and thus would bring online separate  servers with the
STORAGE SERVICE installed. So, do you?''')

is_dummy = yn('''Will this  machine be monitoring an existing  mining script on this machine (but
not starting it)?''')
if is_dummy:
    is_client = False

if not is_client and not is_dummy and not is_relay and not is_storage:
    sys.exit()

print(colors.BLUE + 'This server %s %s a cryptocurrency mining script.' % ((colors.GREEN + '[WILL]' if is_client or is_dummy else colors.RED + '[WILL NOT]') + colors.BLUE, 'run' if not is_dummy else 'monitor (on this machine)'))
print('This server %s host (or host a backup of) the ivy dashboard.' % ((colors.GREEN + '[WILL]' if is_relay else colors.RED + '[WILL NOT]') + colors.BLUE))
print('This server %s store (or backup) your mining farm\'s data.' % ((colors.GREEN + '[WILL]' if is_storage else colors.RED + '[WILL NOT]') + colors.BLUE))

is_good = yn('Okay! Before I continue, is this correct?')
if not is_good:
    sys.exit()

data = {}

if is_client or is_dummy:
    data['client'] = {}
    print('What is the name of the mining rig? ', end='', flush=True)
    data['client']['name'] = input()

    if is_dummy:
        data['client']['dummy'] = True


if is_relay:
    data['relay'] = {}
    print('Because this is a RELAY SERVER, give me a moment to see if any already exist...' + colors.ENDC)
    print('%d RELAY SERVER\'s found. This server\'s priority has been set to %d.' % (0, 0))

if is_storage:
    data['storage'] = {'type': 'file'}

print('Saving configuration...')

if not os.path.exists('/etc/ivy/'):
    os.makedirs('etc/ivy/')

with open('/etc/ivy/config.json', 'w') as f:
    json.dump(data, f)

print('Done. Ivy has been installed.')
