# debian-distro-template

A template for making your own Debian 13 (trixie, amd64) based distro. Pick an
edition at build time and get a bootable live ISO for it:

```sh
tools/build-iso.sh --desktop xfce        # → out/zyphoros-1.0-xfce-amd64.iso
```

Editions live in `desktops/`:

| Edition | What you get |
|---|---|
| `minimal` | Console only: kernel, NetworkManager (`nmtui`), sudo, automatic security updates. |
| `xfce` | Xfce with the LightDM login screen and screen lock, one bottom panel (Whisker menu, windows, tray, sound, battery, notifications, clock), Greybird theme, PipeWire sound, Bluetooth, printing, update notifications, Firefox, LibreOffice and everyday apps, and the Calamares installer. |

GNOME and KDE Plasma editions are next. Every edition's live session logs in
automatically; installed systems ask for the password at the login screen,
unless "Log in automatically" was ticked in the installer.

## Build host

Debian 13 with:

```sh
sudo apt install live-build build-essential debhelper dpkg-dev devscripts lintian \
    xorriso wget qemu-system-x86 qemu-utils ovmf python3
```

A build takes 15–50 minutes depending on the edition and asks for sudo once.

## Make it your distro

The name and version live in
`packages/DISTRO_ID-branding/usr/lib/DISTRO_ID-release`; the build settings
(Debian mirror, live user, hostname) in `distro.conf`.

A complete walkthrough is under [Example](#example) below.

**Artwork.** `tools/make-artwork.py` draws simple placeholder artwork (a
gradient wallpaper, login and GRUB backgrounds, a round logo) into
`packages/DISTRO_ID-artwork/` and the installer's branding. Replace those
files with your own (same names and sizes), or change the colors at the top
of the script and run it again.

## Commands

```sh
tools/build-iso.sh --desktop NAME [--purge]    # build one edition (--purge: fresh download cache)
tools/build-iso.sh --desktop NAME --config-only   # assemble build/NAME and run lb config, no root
tools/boot-test.py --desktop NAME [-v]         # headless QEMU boot test on the serial console
tools/test-iso.sh --desktop NAME [--live|--install|--disk] [--uefi|--bios] [--reset]   # QEMU window
sh packages/build.sh                           # build all packages into packages/.build/debs/
```

Boot-test exit codes: 0 pass, 1 a check failed, 2 setup error, 3 no login.
Its results go to `boot-test/NAME/`; test disks for `test-iso.sh` to `.test-vm/NAME/`.

## How it fits together

```
distro.conf          build settings for every edition
auto/config          all lb config options (reads distro.conf, the release file, desktop.conf)
config/              live-build config shared by every edition
desktops/NAME/       one edition: desktop.conf, optional config/ overlay
installer/config/    live-build config for editions with INSTALLER=yes
packages/            the distro's own Debian packages (native, Architecture: all)
tools/               build and test scripts
```

`tools/build-iso.sh --desktop NAME` assembles `build/NAME/` from `auto/`,
`config/`, `installer/config/` (only with `INSTALLER=yes`) and
`desktops/NAME/config/`, fills in the `@...@` words in hooks and
package lists, builds `packages/` into `build/NAME/config/packages.chroot/`
(live-build installs them from there), then runs `lb config` and `lb build`
there. Each edition keeps its own chroot and download cache.

**Editions are meta-packages.** `desktop.conf`'s `META=xyz` makes the image
install `DISTRO_ID-xyz`. Its **Depends** are what the edition can't work without;
its **Recommends** are removable apps and tools. Installed systems get changes
to an edition through apt, and a user can remove any Recommends without
losing the desktop.

**Recommends.** The image is built with `--apt-recommends false`, so it contains
exactly what the distro's packages list: `0050-recommends` installs the
Recommends of every installed `DISTRO_ID-*` package, but not those of Debian's
packages. A package that Debian only recommends and the system needs must be
in a meta-package's Depends or in `config/package-lists/`, or it is silently
missing. Put must-haves in `REQUIRED` (in `desktop.conf` or
`0010-sanity`) so the build fails early instead. `0900-apt-recommends` turns
Recommends back on for installed systems, like plain Debian.

**Packages.**

| Package | What it does |
|---|---|
| `DISTRO_ID-branding` | The distro's name in os-release and the console login banner (below). |
| `DISTRO_ID-base` | Meta-package of every edition: kernel, systemd, NetworkManager, sudo, updates, console tools. |
| `DISTRO_ID-artwork` | A desktop-base theme made the active one, so the wallpaper, lock screen, LightDM/SDDM login background and the installed system's GRUB menu show your artwork; the logo icon. |
| `DISTRO_ID-desktop-xfce` | Meta-package of the Xfce edition. |
| `DISTRO_ID-settings-xfce` | Xfce defaults in `/etc/xdg/DISTRO_ID-xfce/` (panel, theme, fonts, default apps), read before Debian's `/etc/xdg` in Xfce sessions; LightDM and greeter settings. |
| `DISTRO_ID-installer` | Calamares settings and branding, "Install" in the menu and on the live desktop. Live image only: installing removes it, Calamares and the live-system packages. |

**Installer.** Editions with `INSTALLER=yes` get `installer/config/`: the
installer package, plus GRUB for UEFI (shim and signed GRUB, so Secure Boot
works) and BIOS in a package pool on the ISO (`*.list.binary`). The installer
installs the right one from there, so it works without a network. The GRUB
menu of installed systems says "Debian GNU/Linux": the signed GRUB needs the
EFI folder `debian`, and Debian names that folder after the menu entry.

**Branding.** `DISTRO_ID-branding` diverts `base-files`' `/usr/lib/os-release`,
`/etc/issue` and `/etc/issue.net` and generates them from the release file:
`PRETTY_NAME` and `VARIANT` show your distro, `ID=debian` stays so software
that detects Debian keeps working.

## Adding an edition

1. `desktops/NAME/desktop.conf`: `DESKTOP_NAME`, `META`, `INSTALLER`,
   `BOOT_OPTIONS`, `REQUIRED`, `DISPLAY_MANAGER` and `SESSION_PROCESSES` (what
   the boot test waits for as proof of autologin), as in
   `desktops/xfce/desktop.conf`.
2. `packages/DISTRO_ID-META/`: the edition's meta-package, depending on
   `DISTRO_ID-base` (and `DISTRO_ID-artwork` for a desktop). Put the
   desktop's defaults in a `DISTRO_ID-settings-NAME` package.
3. Edition checks for the boot test: `EDITION_CHECKS` in `tools/boot-test.py`.
4. Optionally `desktops/NAME/config/`: package lists, hooks (numbered 0001–0999,
   `#!/bin/sh` + `set -e`, executable) or includes for this edition only.
   Prefer packages: files dropped into the image never update after install.

## Releasing

1. Bump `DISTRO_VERSION` in the release file and add a changelog entry to the
   branding package: `cd packages/DISTRO_ID-branding && dch -i -D trixie "Version X.Y."`.
2. Any content change to a package needs a changelog entry too
   (`dch -i -D trixie "What changed."`, never `UNRELEASED`), or apt won't upgrade it.
3. `tools/build-iso.sh --desktop NAME --purge` for each edition, then boot-test it.


## Example

The Xfce edition, from build to release.

```sh
# 1. Optional: change the version, mirror, live user or hostname
nano packages/zyphoros-branding/usr/lib/zyphoros-release    # DISTRO_VERSION="1.0"
nano distro.conf                                            # MIRROR, LIVE_USER, LIVE_HOSTNAME

# 2. Build the Xfce ISO (asks for sudo once, about 30-50 min)
tools/build-iso.sh --desktop xfce
#   → out/zyphoros-1.0-xfce-amd64.iso and out/SHA256SUMS

# 3. Test it
tools/boot-test.py --desktop xfce -v              # headless: autologin, lightdm, settings, network
tools/test-iso.sh --desktop xfce --live           # QEMU window: try the live desktop
tools/test-iso.sh --desktop xfce --install --uefi # install with Calamares to a test disk
tools/test-iso.sh --desktop xfce --disk           # boot the installed system (login through LightDM)
```

Changing what's in it: edit the meta-package, add a changelog entry, rebuild.

```sh
nano packages/zyphoros-desktop-xfce/debian/control     # Depends = the session, Recommends = apps
cd packages/zyphoros-desktop-xfce && dch -i -D trixie "Add GIMP." && cd -
tools/build-iso.sh --desktop xfce
```

A release: bump the version, then build with a fresh download cache.

```sh
cd packages/zyphoros-branding && dch -i -D trixie "Version 1.1." && cd -
tools/build-iso.sh --desktop xfce --purge
```

Two quick checks before a full build: `tools/build-iso.sh --desktop xfce
--config-only` checks the configuration without root, and
`sh packages/build.sh` builds only the packages.

## License

GPL-3.0-or-later (`LICENSE`). Each package has a DEP-5 `debian/copyright`.
