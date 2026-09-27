# Validation status

## Completed in the build environment

- Python compilation of the application and standard-library model.
- Shell syntax checks for installer, session launcher, RetroPie build and image-capture scripts.
- Twelve automated tests covering profile creation, optional/no PIN, persistence across new Store instances, salted PIN verification, malformed input, persistent lockout delays, corrupt-state fail-closed behavior, argument validation, all requested systems, UI gate behavior, all app windows, theme persistence and launch routing. Native/privileged processes are intercepted in UI tests.
- Offscreen rendering of actual Qt widgets: profile screen, light shelf, dark shelf and Settings. A dark-mode contrast defect was repaired after visual inspection.
- Self-extracting payload checksum and extraction/source comparison.
- Read-only rejection check: the Pi installer rejects this non-ARM64 environment before package or system changes.

These checks do not certify the system on actual Raspberry Pi hardware. Screenshots are Qt renders, not photographs of a running Pi.

## On-Pi acceptance checklist

1. Install on a spare Pi 4 card; record OS codename and package versions. Reboot and confirm `play` autologin opens profile creation first.
2. Create a profile with leading-zero PIN; reboot; reject a wrong code and accept the correct one. Reboot a no-PIN profile and confirm direct shelf entry.
3. Verify themes, wallpaper, app windows, focus, launcher search and display scaling on the TV.
4. Pair to Sunshine; inspect the PC app list; launch Steam and Desktop. Verify hardware decoding, 1080p60/H.264/20 Mb/s, audio, controller forwarding, exit shortcuts, TTY switching and shelf return.
5. Check desktop-mode streaming fallback and optional RDP with interactive credentials.
6. Test NetworkManager and Bluetooth controller setup, HDMI volume, persistent resolution, timeout rollback, and the TV's overscan behavior.
7. Confirm SSH is initially off; set the Linux password, explicitly enable/disable SSH, and verify updates preserve the selected state.
8. Review every RetroPie module result. Launch EmulationStation as `play`, map the controller, and test user-supplied games/BIOS for each system. Native ARM64 source builds may fail individually.
9. Test Chromium/cloud eligibility, local files, USB mounting, and SMB authentication on the target network.
10. Capture the powered-off card to `.img.xz`, verify its checksum, flash a second sufficiently large card through Imager, and boot it. No boot-tested image was produced in the build environment.
