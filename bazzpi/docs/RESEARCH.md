# Research and compatibility notes

Checked during this build on September 26–27, 2026. Upstream sources change; the Pi installer resolves current packages and records actual build results. Community reports were used to identify usability needs, not as proof of compatibility.

## Primary sources used for implementation

- [Moonlight: Raspberry Pi 4 installation](https://github.com/moonlight-stream/moonlight-docs/wiki/Installing-Moonlight-Qt-on-Raspberry-Pi-4): Bookworm-or-later requirement, official package repository, direct-console performance, HDMI/audio guidance and the recommendation to keep desktop output at 1080p or below. Bazzpi supplies a TTY launch path, retains 1080p defaults, and exposes audio controls.
- [Moonlight command-line parser](https://github.com/moonlight-stream/moonlight-qt/blob/master/app/cli/commandlineparser.cpp): verified `pair --pin`, `list`, `stream`, exact `H.264` codec spelling, bitrate in Kbps, custom resolution, fullscreen mode, and hostname/app positional arguments against source.
- [RetroPie manual installation](https://retropie.org.uk/docs/Manual-Installation/): manual installation guidance and release caveats. Bazzpi uses the requested ARM64 environment while surfacing module failures rather than assuming all components are supported.
- [RetroPie setup entry point](https://github.com/RetroPie/RetroPie-Setup/blob/master/retropie_packages.sh): user selection via `SUDO_USER` / `__user`. The build explicitly targets `play` to avoid placing ROM paths under root.
- [RetroPie EmulationStation wrapper](https://github.com/RetroPie/RetroPie-Setup/blob/master/scriptmodules/supplementary/emulationstation.sh): EmulationStation is launched as a regular user, not root.
- [RetroPie DeSmuME module](https://github.com/RetroPie/RetroPie-Setup/blob/master/scriptmodules/libretrocores/lr-desmume.sh): ARM64 builds disable JIT. This supports the visible Nintendo DS performance caveat.
- [Sunshine troubleshooting](https://github.com/LizardByte/Sunshine/blob/master/docs/troubleshooting.md): network stability and packet loss matter for low-latency streaming. Bazzpi exposes basic connection diagnostics and lower-bandwidth presets. Ping/TCP checks are not a streaming benchmark.
- [Raspberry Pi Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html): custom image workflow; the provided capture tool outputs compressed raw `.img.xz`, not an ISO.
- [Xbox cloud gaming](https://www.xbox.com/en-US/cloud-gaming): browser/plan and platform requirements. The requested Ultimate setup is documented without claiming it is the only currently available cloud plan.

## Community reading and resulting additions

- [Reddit: The Perfect Moonlight Setup on Raspberry Pi](https://www.reddit.com/r/MoonlightStreaming/comments/1ju40yv/the_perfect_moonlight_setup_on_raspberry_pi/): console-style use and wired networking informed the controller-first launcher and direct-console option. Technical choices were checked against Moonlight's own documentation.
- [RetroPie forum: Getting the best N64 experience on a Pi 4](https://retropie.org.uk/forum/topic/25112/getting-the-best-n64-experience-on-a-pi-4/140): illustrates title/core variability. Bazzpi keeps the requested “hit or miss” category and reports installation separately.
- [Raspberry Pi forum: Moonlight network/frame-drop discussion](https://forums.raspberrypi.com/viewtopic.php?t=213184): used as a troubleshooting theme, not as a current benchmark. The diagnostics view includes connectivity, temperature and power/throttling output instead of applying speculative overclocks or network tunings.

No automatic overclocking, undervolting, firewall exposure, third-party ROM packs, or unofficial controller kernel modules are applied.
