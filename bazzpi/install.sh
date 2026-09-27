#!/bin/bash
# Bazzpi 1.0 — Raspberry Pi OS 64-bit native installer.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RETRO=true
case "${1:-}" in
  --skip-retropie) RETRO=false ;;
  --help) echo 'sudo bash install.sh [--skip-retropie]'; exit 0 ;;
  '') ;;
  *) echo 'Unknown option. Use --help.'; exit 2 ;;
esac
[[ $EUID == 0 ]] || { echo 'Run with sudo bash install.sh'; exit 1; }
[[ $(dpkg --print-architecture) == arm64 ]] || { echo 'This installer requires Raspberry Pi OS 64-bit (arm64).'; exit 1; }
if [[ ${BAZZPI_IMAGE_BUILD:-0} != 1 ]]; then
    [[ -r /proc/device-tree/model ]] && grep -q 'Raspberry Pi 4' /proc/device-tree/model || { echo 'This installer targets a Raspberry Pi 4.'; exit 1; }
else
    [[ -f /BAZZPI_IMAGE_ROOT ]] || { echo 'Image build must run inside the prepared image root.'; exit 1; }
fi
source /etc/os-release
[[ "${VERSION_CODENAME:-}" == bookworm || "${VERSION_CODENAME:-}" == trixie ]] || { echo 'Use Raspberry Pi OS Bookworm or Trixie 64-bit. Other releases are not validated.'; exit 1; }
[[ -e /etc/rpi-issue ]] || { echo 'Use Raspberry Pi OS, not a generic Debian image.'; exit 1; }
mkdir -p /var/log/bazzpi
exec > >(tee -a /var/log/bazzpi/install.log) 2>&1
trap 'echo "Install stopped at line $LINENO. Fix the error above, then rerun this installer. See /var/log/bazzpi/install.log."' ERR
exec 8>/run/bazzpi-install.lock
flock -n 8 || { echo 'Another Bazzpi install is running.'; exit 1; }
if [[ $(df -Pk / | awk 'NR==2 {print $4}') -lt 6291456 ]]; then
    echo 'At least 6 GiB free space is required; 16+ GiB free is recommended for the full source builds.'; exit 1
fi
FIRST=true
[[ -f /var/lib/bazzpi/installed ]] && FIRST=false
apt-get update
# X11 is deliberate: a small native shelf plus a stable window manager.
DEBIAN_FRONTEND=noninteractive apt-get install -y \
 python3 python3-pyqt5 python3-xlib python3-evdev \
 xserver-xorg xinit x11-xserver-utils x11-utils openbox lightdm \
 xterm xdotool arandr pcmanfm gvfs-backends gvfs-fuse \
 network-manager blueman bluez lxpolkit pavucontrol pulseaudio-utils \
 remmina remmina-plugin-rdp openssh-server sudo raspi-config \
 git curl ca-certificates lsb-release unzip xz-utils kbd fonts-dejavu-core
if apt-cache show chromium >/dev/null 2>&1; then apt-get install -y chromium
else apt-get install -y chromium-browser; fi
# Retain PipeWire if already installed; Lite needs an audio server.
if ! dpkg-query -W -f='${Status}' pipewire-pulse 2>/dev/null | grep -q 'install ok installed'; then
    apt-get install -y pulseaudio
fi
if ! id play >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash play
    # Password remains locked. Autologin works via LightDM's dedicated PAM service.
fi
for group in audio video render input plugdev netdev bluetooth; do
    getent group "$group" >/dev/null && usermod -aG "$group" play
done
# The shelf account is not granted blanket passwordless sudo.
mkdir -p /opt/bazzpi /var/lib/bazzpi /etc/lightdm/lightdm.conf.d /usr/share/xsessions
if [[ -f /opt/bazzpi/app/shelf.py ]]; then
    tar -czf "/var/lib/bazzpi/previous-$(date +%Y%m%d-%H%M%S).tar.gz" -C /opt bazzpi
fi
cp -a "$ROOT_DIR/app" "$ROOT_DIR/system" "$ROOT_DIR/docs" /opt/bazzpi/
chown -R root:root /opt/bazzpi
chmod -R go-w /opt/bazzpi
chmod 755 /opt/bazzpi/system/*.sh /opt/bazzpi/system/bazzpi-admin
install -o root -g root -m 755 /opt/bazzpi/system/bazzpi-admin /usr/local/sbin/bazzpi-admin
printf 'play ALL=(root) NOPASSWD: /usr/local/sbin/bazzpi-admin\n' > /etc/sudoers.d/bazzpi
chmod 440 /etc/sudoers.d/bazzpi
visudo -cf /etc/sudoers.d/bazzpi
cat > /usr/share/xsessions/bazzpi.desktop <<'EOF'
[Desktop Entry]
Name=Bazzpi
Comment=Living-room shelf
Exec=/opt/bazzpi/system/session.sh
Type=Application
DesktopNames=Bazzpi
EOF
if [[ -f /etc/lightdm/lightdm.conf && ! -f /var/lib/bazzpi/lightdm.conf.before ]]; then
    cp -a /etc/lightdm/lightdm.conf /var/lib/bazzpi/lightdm.conf.before
fi
# Main LightDM config overrides snippets. Set seat keys there as well.
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/etc/lightdm/lightdm.conf')
t=p.read_text() if p.exists() else ''
# Retain unrelated settings, replace any conflicting active session/autologin keys.
t=re.sub(r'(?m)^(\s*)(autologin-user|autologin-session|user-session|autologin-user-timeout)\s*=.*$',r'# Bazzpi overrides \2',t)
t+='\n[Seat:*]\nautologin-user=play\nautologin-user-timeout=0\nautologin-session=bazzpi\nuser-session=bazzpi\n'
p.write_text(t)
PY
# A remembered per-user session must also select Bazzpi.
install -d -o play -g play /home/play/.config /home/play/.local/share /home/play/RetroPie/BIOS /home/play/RetroPie/roms
printf '[Desktop]\nSession=bazzpi\n' > /home/play/.dmrc
chown play:play /home/play/.dmrc
if [[ -f /var/lib/AccountsService/users/play ]]; then
    sed -i '/^XSession=/d' /var/lib/AccountsService/users/play
    sed -i '/^\[User\]/a XSession=bazzpi' /var/lib/AccountsService/users/play
fi
# Official Moonlight package source. Download visibly and fail closed on HTTP errors.
repo_script=$(mktemp)
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
 https://dl.cloudsmith.io/public/moonlight-game-streaming/moonlight-qt/setup.deb.sh -o "$repo_script"
distro=raspbian codename="$VERSION_CODENAME" bash "$repo_script"
rm -f "$repo_script"
apt-get update
apt-get install -y moonlight-qt
/usr/local/sbin/bazzpi-admin gpu 128
systemctl enable NetworkManager bluetooth
if $FIRST; then
    systemctl disable --now ssh || true
    rm -f /boot/ssh /boot/ssh.txt /boot/firmware/ssh /boot/firmware/ssh.txt
fi
# Preserve a user's explicit SSH choice on subsequent Bazzpi updates.
systemctl set-default graphical.target
# Do not restart the display manager under an active installer.
if [[ -e /etc/systemd/system/display-manager.service ]]; then
    cp -a /etc/systemd/system/display-manager.service /var/lib/bazzpi/display-manager.before 2>/dev/null || true
fi
ln -sfn /lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
systemctl enable lightdm
/usr/bin/python3 -I - <<'PY'
from pathlib import Path
import pwd,os,sys
sys.path.insert(0,'/opt/bazzpi/app')
from model import SYSTEMS
u=pwd.getpwnam('play')
for folder in {s[1] for s in SYSTEMS}:
    p=Path('/home/play/RetroPie/roms')/folder;p.mkdir(parents=True,exist_ok=True);os.chown(p,u.pw_uid,u.pw_gid)
PY
retro_status=0
if $RETRO; then
    /opt/bazzpi/system/install-retropie.sh || retro_status=$?
else
    echo 'RetroPie deferred. Use its shelf icon → Install / retry emulator builds.'
fi
printf 'Bazzpi 1.0\n' > /var/lib/bazzpi/installed
printf '\nBazzpi installed. Reboot with: sudo reboot\n'
echo 'Next boot: the play account opens the profile screen. No profile was pre-created.'
echo 'HDMI: use the socket next to the USB-C power connector.'
if [[ $retro_status != 0 ]]; then
    echo 'RetroPie had build failures. The shelf is installed; see /var/log/bazzpi/retropie-modules.tsv and retry from RetroPie.'
fi
