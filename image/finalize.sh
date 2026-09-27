#!/bin/bash
set -Eeuo pipefail
[[ -f /BAZZPI_IMAGE_ROOT ]] || { echo 'Not an image build root.'; exit 1; }
# Require all requested packages/configurations, not just the launcher's files.
python3 -I - <<'PY'
import sys,subprocess
from pathlib import Path
sys.path.insert(0,'/opt/bazzpi/app')
from model import SYSTEMS
required=['moonlight-qt','chromium','python3-pyqt5','remmina','pcmanfm','lightdm']
for pkg in required:
    status=subprocess.check_output(['dpkg-query','-W','-f=${Status}',pkg],text=True)
    assert status=='install ok installed',pkg
report=Path('/var/log/bazzpi/retropie-modules.tsv').read_text()
results=dict(line.split('\t',1) for line in report.splitlines()[1:] if '\t' in line)
for name,folder,module in SYSTEMS:
    assert results.get(module)=='succeeded',(name,module,results.get(module))
    assert Path('/opt/retropie/configs',folder,'emulators.cfg').is_file(),name
assert Path('/usr/bin/emulationstation').exists()
assert not Path('/home/play/.config/bazzpi/state.json').exists()
PY
# Turn the official base's OS-account onboarding into the requested Bazzpi first screen.
for unit in userconfig.service userconfig-pi.service; do systemctl disable "$unit" 2>/dev/null || true; done
systemctl disable ssh.service 2>/dev/null || true
# No preset password and no remotely accessible account in a distributed image.
passwd -l play
passwd -l root
printf 'bazzpi\n' > /etc/hostname
sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tbazzpi/' /etc/hosts
# Restore any getty configuration inherited from the base to normal login behavior.
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
# Base first-boot resize script is retained; remove only account-customization arguments.
python3 - <<'PY'
from pathlib import Path
p=Path('/boot/firmware/cmdline.txt')
parts=p.read_text().split()
parts=[s for s in parts if s not in ('systemd.run=/boot/firstrun.sh','systemd.run=/boot/firmware/firstrun.sh','systemd.run_success_action=reboot','systemd.unit=kernel-command-line.target')]
p.write_text(' '.join(parts)+'\n')
PY
rm -f /boot/firmware/userconf /boot/firmware/userconf.txt /boot/firmware/ssh /boot/firmware/ssh.txt
rm -f /etc/ssh/ssh_host_*
# ssh-keygen runs before an explicitly enabled SSH server, never exposes SSH by itself.
mkdir -p /etc/systemd/system/ssh.service.d
printf '[Service]\nExecStartPre=/usr/bin/ssh-keygen -A\n' > /etc/systemd/system/ssh.service.d/bazzpi-keys.conf
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id
rm -f /var/lib/systemd/random-seed
apt-get clean
# Remove compiler scratch data; preserve RetroPie setup scripts, runtime and logs.
rm -rf /opt/retropie-setup/tmp/build /opt/retropie-setup/tmp/swap
find /var/lib/apt/lists -type f -delete
# Save a dependency manifest before completing the image.
dpkg-query -W > /var/log/bazzpi/package-manifest.tsv
