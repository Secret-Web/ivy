import os
import time
import signal


if not os.path.exists('/etc/ivy/.pid'):
    exit(0)

pid = None

with open('/etc/ivy/.pid', 'r') as f:
    pid = int(f.read())

if pid is not None:
	os.kill(pid, signal.SIGINT)

    while os.kill(pid, 0):
        time.sleep(1)