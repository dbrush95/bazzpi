# Bazzpi — Raspberry Pi 4 living-room shelf

This repository contains the Bazzpi shelf and a native ARM64 build for a fully installed Raspberry Pi OS card image. Check the Actions tab for build status. A flashable image is available only after a successful build; source ZIPs are not card images.

The workflow starts from the official Bookworm 64-bit Lite image, verifies the upstream checksum, preserves its boot firmware and partition identifiers, expands the root filesystem, installs the shelf and all third-party packages, runs the official RetroPie basic install plus every requested emulator module, checks module results and system configuration files, prepares the play account for first-boot profile setup, checks both filesystems and compresses to `Bazzpi-Pi4.img.xz`.

The final image upload only happens after all build stages succeed. A module failure or six-hour runner limit stops the job and retains available diagnostics; it never labels a partial install as complete. Real Pi boot, HDMI and controller testing is separate from image assembly.

## Required build environment

The included GitHub workflow selects `ubuntu-24.04-arm` and needs permission to run Actions. Private repositories consume the account's Actions allowance. The build requires native ARM64, root access to mount loop devices, internet access and at least 12 GiB free storage; 24+ GiB is preferred. Full emulator compilation may exceed a standard runner's time or space limit; a larger/self-hosted ARM64 runner can be used if necessary.

The build starts when application, image or workflow files are pushed to `main`. It can also be started manually from Actions → Build complete Bazzpi Pi 4 image → Run workflow. After success, download the `Bazzpi-Pi4-Complete-Image` artifact, extract the GitHub artifact ZIP, and select the contained `.img.xz` using Raspberry Pi Imager's Use custom option. Use a 32 GB or larger card. No first-boot package installation is scheduled.

The workflow is a reviewable build candidate: shell syntax and structure are checked locally, and the full build executes on the GitHub runner, which supplies the required mounting/ARM environment. Further fixes may be necessary based on the runner build log. In particular, all ARM64 RetroPie modules must pass before an image can be delivered as complete.

## Source references

- https://github.com/moonlight-stream/moonlight-docs/wiki/Installing-Moonlight-Qt-on-Raspberry-Pi-4
- https://github.com/RetroPie/RetroPie-Setup/blob/master/scriptmodules/system.sh
- https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-05-13/
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

The source retains Bazzpi's native installer but adds an explicit chroot-only image-build mode. It does not remove host authorization checks or allow the installer to run on arbitrary architectures.
