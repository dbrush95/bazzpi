#!/bin/bash
# Builds a fully populated SD image on a privileged ARM64 Linux build runner.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[[ $EUID == 0 ]] || { echo 'Run with sudo.'; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo 'A native ARM64 Linux runner is required.'; exit 1; }
repo_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
work_dir=$(mktemp -d /var/tmp/bazzpi-image.XXXXXXXX)
out_dir="$repo_dir/output"
mkdir -p "$out_dir/logs"
image_path="$work_dir/Bazzpi-Pi4.img"
root_dir="$work_dir/root"
loop_device=''
cleanup() {
    code=$?
    trap - EXIT
    if [[ -d "$root_dir/var/log/bazzpi" ]]; then cp -a "$root_dir/var/log/bazzpi/." "$out_dir/logs/" || true; fi
    for target in sys proc dev boot/firmware ''; do
        if mountpoint -q "$root_dir${target:+/$target}"; then umount -R "$root_dir${target:+/$target}" || true; fi
    done
    if [[ -n "$loop_device" ]]; then losetup -d "$loop_device" || true; fi
    # Only delete this script's uniquely created build directory after all mounts are gone.
    if ! findmnt -rn -o TARGET | grep -Fq "$work_dir/"; then rm -rf -- "$work_dir"; fi
    exit "$code"
}
trap cleanup EXIT
apt-get update
apt-get install -y curl ca-certificates xz-utils util-linux fdisk e2fsprogs dosfstools rsync git
# The image is sparse while building. Refuse inadequate free space up front.
[[ $(df -Pk "$work_dir" | awk 'NR==2 {print $4}') -ge 12582912 ]] || { echo 'Need at least 12 GiB free; 24+ GiB is preferred.'; exit 1; }
base_name=2025-05-13-raspios-bookworm-arm64-lite.img.xz
base_url="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-05-13/$base_name"
curl --fail --location --retry 3 --proto '=https' "$base_url" -o "$work_dir/$base_name"
curl --fail --location --retry 3 --proto '=https' "$base_url.sha256" -o "$work_dir/base.sha256"
expected=$(awk 'NR==1 {print $1}' "$work_dir/base.sha256")
[[ "$expected" =~ ^[a-fA-F0-9]{64}$ ]] || { echo 'Invalid upstream SHA256 file.'; exit 1; }
printf '%s  %s\n' "$expected" "$work_dir/$base_name" | sha256sum -c -
xz -dc "$work_dir/$base_name" > "$image_path"
rm -- "$work_dir/$base_name"
# Preserve the official partition layout and boot firmware; enlarge only partition 2.
truncate -s 16G "$image_path"
printf ',+\n' | sfdisk --no-reread -N 2 "$image_path"
loop_device=$(losetup --find --show --partscan "$image_path")
udevadm settle
fsck_code=0
e2fsck -fy "${loop_device}p2" || fsck_code=$?
[[ $fsck_code -le 1 ]] || exit "$fsck_code"
resize2fs "${loop_device}p2"
mkdir -p "$root_dir"
mount "${loop_device}p2" "$root_dir"
mkdir -p "$root_dir/boot/firmware"
mount "${loop_device}p1" "$root_dir/boot/firmware"
# The chroot gets no host /run, so systemctl cannot reach the runner's service manager.
mount --rbind /dev "$root_dir/dev"
mount --make-rslave "$root_dir/dev"
mount -t proc proc "$root_dir/proc"
mount --rbind /sys "$root_dir/sys"
mount --make-rslave "$root_dir/sys"
if [[ -e "$root_dir/etc/resolv.conf" || -L "$root_dir/etc/resolv.conf" ]]; then
    mv "$root_dir/etc/resolv.conf" "$root_dir/etc/resolv.conf.bazzpi-original"
fi
cp -L /etc/resolv.conf "$root_dir/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root_dir/usr/sbin/policy-rc.d"
chmod 755 "$root_dir/usr/sbin/policy-rc.d"
touch "$root_dir/BAZZPI_IMAGE_ROOT"
mkdir -p "$root_dir/tmp/bazzpi-source"
cp -a "$repo_dir/bazzpi/." "$root_dir/tmp/bazzpi-source/"
# First install the shelf; then require the entire native emulator build to succeed.
chroot "$root_dir" /usr/bin/env BAZZPI_IMAGE_BUILD=1 DEBIAN_FRONTEND=noninteractive \
    /bin/bash /tmp/bazzpi-source/install.sh --skip-retropie
# Upstream RetroPie supports explicit platform selection for chroot/image builds.
chroot "$root_dir" /usr/bin/env __platform=rpi4 __has_kms=1 __chroot=1 \
    DEBIAN_FRONTEND=noninteractive /opt/bazzpi/system/install-retropie.sh
# Any build failure above aborts. Never upload an incomplete image as a full release.
cp "$repo_dir/image/finalize.sh" "$root_dir/tmp/finalize-bazzpi.sh"
chroot "$root_dir" /bin/bash /tmp/finalize-bazzpi.sh
cp -a "$root_dir/var/log/bazzpi/." "$out_dir/logs/"
rm -f "$root_dir/etc/resolv.conf"
if [[ -e "$root_dir/etc/resolv.conf.bazzpi-original" || -L "$root_dir/etc/resolv.conf.bazzpi-original" ]]; then
    mv "$root_dir/etc/resolv.conf.bazzpi-original" "$root_dir/etc/resolv.conf"
fi
rm -f "$root_dir/usr/sbin/policy-rc.d" "$root_dir/BAZZPI_IMAGE_ROOT" "$root_dir/tmp/finalize-bazzpi.sh"
rm -rf "$root_dir/tmp/bazzpi-source"
sync
for target in sys proc dev boot/firmware ''; do umount -R "$root_dir${target:+/$target}"; done
fsck_code=0
e2fsck -fy "${loop_device}p2" || fsck_code=$?
[[ $fsck_code -le 1 ]] || exit "$fsck_code"
fsck.vfat -n "${loop_device}p1"
losetup -d "$loop_device"; loop_device=''
xz -T2 -3 -c "$image_path" > "$out_dir/Bazzpi-Pi4.img.xz.partial"
xz -t "$out_dir/Bazzpi-Pi4.img.xz.partial"
mv "$out_dir/Bazzpi-Pi4.img.xz.partial" "$out_dir/Bazzpi-Pi4.img.xz"
(cd "$out_dir" && sha256sum Bazzpi-Pi4.img.xz > Bazzpi-Pi4.img.xz.sha256)
echo 'Image assembled and filesystem-checked. A real Pi boot test is still required.'
