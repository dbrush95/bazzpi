#!/bin/bash
# Read an OFFLINE card on a separate Linux machine; writes only the named image file.
set -Eeuo pipefail
[[ $EUID == 0 && $# == 2 ]] || { echo 'Usage: sudo bash capture-card.sh /dev/sdX /path/Bazzpi-Pi4.img.xz'; exit 2; }
source_device=$(readlink -f -- "$1")
output_file=$2
[[ -b "$source_device" ]] || { echo 'Source must be a block device.'; exit 1; }
[[ $(lsblk -dn -o TYPE "$source_device") == disk ]] || { echo 'Select the whole SD card, not a partition.'; exit 1; }
[[ "$output_file" == *.img.xz ]] || { echo 'Output must end in .img.xz'; exit 1; }
[[ ! -e "$output_file" ]] || { echo 'Output already exists; refusing to overwrite.'; exit 1; }
# Any mounted descendant implies that this is not an offline card.
if lsblk -nr -o MOUNTPOINTS "$source_device" | grep -q '[^[:space:]]'; then
    echo 'Unmount every partition of the source card first. Never capture your running root disk.';exit 1
fi
output_dir=$(dirname -- "$output_file")
[[ -d "$output_dir" ]] || { echo 'Output directory does not exist.'; exit 1; }
lsblk -o NAME,SIZE,MODEL,TYPE "$source_device"
printf 'Read this card into %s? Type CAPTURE: ' "$output_file"
read -r confirm
[[ "$confirm" == CAPTURE ]] || exit 1
# noclobber protects against races; partial output is clearly named.
set -o noclobber
dd if="$source_device" bs=4M iflag=fullblock status=progress | xz -T0 -3 > "${output_file}.partial"
mv -n -- "${output_file}.partial" "$output_file"
sha256sum "$output_file" > "$output_file.sha256"
echo 'Open Raspberry Pi Imager → Choose OS → Use custom → select the .img.xz file.'
echo 'Destination SD must be at least as large in bytes as the captured card.'
