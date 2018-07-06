import os
import signal


pid = None

with open('/etc/ivy/.pid', 'r') as f:
    pid = int(f.read())

if pid is not None:
	os.kill(pid, signal.SIGINT)

