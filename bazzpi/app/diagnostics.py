#!/usr/bin/python3
import shutil
import socket
import subprocess
import sys
from pathlib import Path

def command(title,args):
    print('\n'+title,flush=True)
    try:
        r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
        print(r.stdout.strip() or f'Exit {r.returncode}',flush=True)
    except (OSError,subprocess.TimeoutExpired) as e:print(e,flush=True)

print('BAZZPI DIAGNOSTICS — no passwords or pairing keys collected',flush=True)
command('OS',['uname','-a'])
command('Network',['nmcli','-t','-f','DEVICE,TYPE,STATE,CONNECTION','device'])
command('Temperature',['vcgencmd','measure_temp'])
command('Power / thermal throttling (0x0 is clear)',['vcgencmd','get_throttled'])
command('SSH status',['systemctl','is-active','ssh'])
command('Audio outputs',['pactl','list','short','sinks'])
command('Storage',['df','-h','/'])
print('\nControllers:', '\n'.join(str(x) for x in Path('/dev/input').glob('js*')) or 'No joystick nodes')
if len(sys.argv)>1 and sys.argv[1]:
    from model import host
    pc=host(sys.argv[1]);command('PC reachability (ICMP may be blocked)',['ping','-c','4','-W','2',pc])
    for port in [47984,47989,47990,48010]:
        try:
            with socket.create_connection((pc,port),timeout=2):print(f'TCP {port}: reachable',flush=True)
        except OSError:print(f'TCP {port}: not reachable',flush=True)
print('\nPrefer wired Ethernet; use the HDMI port next to power.\nUse a stable power supply and cooling. Try 720p60 / 10 Mb/s if frames drop.\nA reachable port does not prove that pairing or video decoding works.',flush=True)
