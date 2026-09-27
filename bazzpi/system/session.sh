#!/bin/bash
set -u
export XDG_CURRENT_DESKTOP=Bazzpi
export QT_QPA_PLATFORM=xcb
xset s off
xset -dpms
openbox --config-file /opt/bazzpi/system/openbox.xml &
wm_pid=$!
lxpolkit &
auth_pid=$!
# Use the already configured audio service (PipeWire or PulseAudio).
if ! pactl info >/dev/null 2>&1; then pulseaudio --start; fi
trap 'kill "$wm_pid" "$auth_pid" 2>/dev/null || true' EXIT
while true; do
    /usr/bin/python3 /opt/bazzpi/app/shelf.py
    result=$?
    # A crash restarts through the profile gate, never into a bare desktop.
    [[ $result == 0 ]] && break
    sleep 2
done
