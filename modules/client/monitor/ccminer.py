import socket

from . import API


class ClaymoreAPI(API):
    async def get_stats(self, host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, 4068))
        s.send('threads\n'.encode("utf-8"))
        data = s.recv(2048).decode("utf-8")
        s.close()

        # GPU=0;BUS=1;CARD=Zotac GTX 1080 Ti;TEMP=64.0;POWER=243724;FAN=41;RPM=0;FREQ=1721;MEMFREQ=5505;GPUF=1987;MEMF=5107;KHS=0.59;KHW=0.00241;PLIM=320000;ACC=5;REJ=0;HWF=0;I=20.0;THR=1048576|GPU=1;BUS=2;CARD=Zotac GTX 1080 Ti;TEMP=62.0;POWER=262408;FAN=35;RPM=0;FREQ=1721;MEMFREQ=5505;GPUF=2012;MEMF=5103;KHS=0.59;KHW=0.00224;PLIM=320000;ACC=6;REJ=0;HWF=0;I=20.0;THR=1048576|GPU=2;BUS=3;CARD=Zotac GTX 1080 Ti;TEMP=63.0;POWER=254924;FAN=41;RPM=0;FREQ=1721;MEMFREQ=5505;GPUF=1987;MEMF=5103;KHS=0.58;KHW=0.00229;PLIM=320000;ACC=7;REJ=0;HWF=0;I=20.0;THR=1048576|

        accepted = 0
        rejected = 0
        hashrate = []

        for info in data.split('|'):
            for entry in info.split(';'):
                if entry.startswith('KHS'):
                    hashrate.append(float(entry.split('=')[1]))
                elif entry.startswith('ACC'):
                    accepted.append(float(entry.split('=')[1]))
                elif entry.startswith('REJ'):
                    rejected.append(float(entry.split('=')[1]))

        return {
            'shares': {
                'accepted': accepted,
                'invalid': 0,
                'rejected': rejected
            },
            'hashrate': hashrate
        }

__api__ = ClaymoreAPI
