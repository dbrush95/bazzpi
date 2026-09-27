#!/bin/bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.'; exit 1; }
exec 9>/run/bazzpi-retropie.lock
flock -n 9 || { echo 'A RetroPie install is already running.'; exit 1; }
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export SUDO_USER=play SUDO_UID="$(id -u play)" SUDO_GID="$(id -g play)" __user=play
unset DISPLAY WAYLAND_DISPLAY
mkdir -p /var/log/bazzpi
exec > >(tee -a /var/log/bazzpi/retropie-install.log) 2>&1
apt-get update
apt-get install -y git
if [[ ! -d /opt/retropie-setup/.git ]]; then
    git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git /opt/retropie-setup
fi
cd /opt/retropie-setup
# Official native basic install. SUDO_USER ensures /home/play, not /root.
status=0
./retropie_setup.sh basic_install || status=1
# Basic install does not contain all requested systems. Try their official modules.
mapfile -t modules < <(/usr/bin/python3 -I -c 'import sys; sys.path.insert(0,"/opt/bazzpi/app"); from model import SYSTEMS; print("\n".join(dict.fromkeys(s[2] for s in SYSTEMS)))')
printf 'module\tresult\n' > /var/log/bazzpi/retropie-modules.tsv
for module in "${modules[@]}"; do
    echo "Building $module for play"
    if ./retropie_packages.sh "$module"; then
        printf '%s\tsucceeded\n' "$module" >> /var/log/bazzpi/retropie-modules.tsv
    else
        printf '%s\tfailed or unsupported on this OS/architecture\n' "$module" >> /var/log/bazzpi/retropie-modules.tsv
        status=1
    fi
done
/usr/bin/python3 -I - <<'PY'
import sys,os,pwd
from pathlib import Path
sys.path.insert(0,'/opt/bazzpi/app')
from model import SYSTEMS
p=pwd.getpwnam('play')
for folder in {s[1] for s in SYSTEMS}:
    path=Path('/home/play/RetroPie/roms')/folder
    path.mkdir(parents=True,exist_ok=True)
    os.chown(path,p.pw_uid,p.pw_gid)
PY
# Do not install ROM packs, ports, BIOS downloads, or change boot to EmulationStation.
echo 'Native build finished. Review /var/log/bazzpi/retropie-modules.tsv for module results.'
exit "$status"
