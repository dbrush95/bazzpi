# Bazzpi — start here

The installer includes the Bazzpi shelf source and downloads Moonlight, native RetroPie and the other required Linux packages. It is designed for **Raspberry Pi 4 + Raspberry Pi OS 64-bit, Bookworm or Trixie**. Bookworm is the preferred baseline. Internet access is required.

## Install

1. Back up your current SD card. For a new card, use Raspberry Pi Imager to install Raspberry Pi OS Lite (64-bit). Configure a Linux username/password and your network; `play` is the shelf username. Leave SSH disabled.
2. Connect a keyboard, controller, and HDMI to the port nearest the Pi's USB-C power socket.
3. Copy `Bazzpi-Pi4-Installer.run` into your home folder on the Pi.
4. In the Pi terminal, run:

```bash
sudo bash ./Bazzpi-Pi4-Installer.run
sudo reboot
```

The native RetroPie build can take hours. Keep the Pi powered and connected. Read the final installer status before rebooting. Any emulator failures are reported in `/var/log/bazzpi/retropie-modules.tsv`.

For a faster initial shelf installation, use this instead:

```bash
sudo bash ./Bazzpi-Pi4-Installer.run --skip-retropie
sudo reboot
```

Then use **RetroPie → Install / retry emulator builds** to finish the long native build.

## First boot

Create your profile with a name and optional four-digit code. A configured code is required on later boots. The Linux user `play` autologins into this screen.

- **Settings → Appearance:** switch light/dark mode or choose a desktop wallpaper.
- **Play:** save your Bazzite PC's address, select Pair PC, and enter the displayed PIN at `https://PC-ADDRESS:47990` on Sunshine. Refresh the app list and launch Steam.
- **Desktop:** defaults to Sunshine's Desktop app. For Bazzite Deck, switch the PC to Desktop Mode once so Sunshine captures KDE. RDP is available in Settings as a second mode.
- **RetroPie:** launches local EmulationStation as `play`. Supply your own game and BIOS files. The folder list and performance labels are included in the app and source documentation.
- **Game Pass:** opens Xbox Cloud Gaming in Chromium. Use Game Pass Ultimate and a controller for the requested setup; games stay in the cloud. Playback depends on Microsoft's browser/device support.
- **Files:** Home, SD card, USB media and an SMB share configured in Settings.

Streaming defaults: **1080p, 60 fps, H.264, 20 Mb/s**. Quit with **Ctrl+Alt+Shift+Q** or hold **Start + Select + LB + RB**.

## What the files are

- `Bazzpi-Pi4-Installer.run`: run this on Raspberry Pi OS; it is not an Imager card image.
- `Bazzpi-Complete-Source.zip`: complete source, full README, all console-folder mappings, research notes, tests, actual Qt UI previews and the card-capture script.
- `SHA256SUMS.txt`: download checksums.

To make an Imager-compatible custom image after installing, power off the Pi, move the SD to a separate Linux machine, and use the included `system/capture-card.sh`. It creates a raw `.img.xz`. Keep a captured card private because it includes that card's credentials and data. Capture before creating a Bazzpi profile if you want that image to show profile setup on first boot.

**Validation:** software tests and offscreen UI checks passed. Real Pi hardware, full native emulator builds, HDMI/controller behavior and a flashed card image still require testing. The four-digit code is a shelf convenience lock, not disk encryption or a secure Linux login replacement.
