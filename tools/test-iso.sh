#!/bin/bash
# Boot an edition's ISO (or its installed test disk) in a QEMU window.
set -euo pipefail

usage() {
    cat <<EOF
Usage: tools/test-iso.sh --desktop NAME [MODE] [FIRMWARE] [OPTIONS]

  --desktop NAME  Edition to test (its ISO and its own test disk)

Modes (default: live):
  --live        Boot the ISO without a disk
  --install     Boot the ISO with a persistent test disk attached, to run Calamares
  --disk        Boot the installed test disk (no ISO)

Firmware (default: --uefi; --disk uses the firmware the disk was installed with):
  --uefi        UEFI (OVMF)
  --bios        Legacy BIOS (SeaBIOS)

Options:
  --iso FILE    ISO to boot (default: newest out/DISTRO_ID-*-NAME-amd64.iso)
  --mem SIZE    Guest RAM (default: 4G)
  --size SIZE   Test disk size when created (default: 20G)
  --reset       Delete the test disk and UEFI variables first
  -h, --help    Show this help

Test disks and UEFI variables are kept in .test-vm/NAME/ (git-ignored).
EOF
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

OVMF_CODE=/usr/share/OVMF/OVMF_CODE_4M.fd
OVMF_VARS=/usr/share/OVMF/OVMF_VARS_4M.fd

desktop=""
mode=live
firmware=""
iso=""
mem=4G
size=20G
reset=0

while [ $# -gt 0 ]; do
    case "$1" in
        --desktop) desktop="${2:?--desktop needs a name}"; shift ;;
        --desktop=*) desktop="${1#--desktop=}" ;;
        --live|--install|--disk) mode="${1#--}" ;;
        --uefi|--bios) firmware="${1#--}" ;;
        --iso) iso="${2:?--iso needs a file}"; shift ;;
        --mem) mem="${2:?--mem needs a size}"; shift ;;
        --size) size="${2:?--size needs a size}"; shift ;;
        --reset) reset=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

die() { echo "$*" >&2; exit 2; }

[ -n "$desktop" ] || { usage >&2; exit 2; }
desktop="${desktop,,}"   # editions are lower case
[ -f "$ROOT/desktops/$desktop/desktop.conf" ] || die "No edition '$desktop' in desktops/."
. "$ROOT/distro.conf"   # DISTRO_ID

STATE="$ROOT/.test-vm/$desktop"
DISK="$STATE/disk.qcow2"
VARS="$STATE/OVMF_VARS.fd"
FW_FILE="$STATE/firmware"

command -v qemu-system-x86_64 >/dev/null || die "Install QEMU: sudo apt install qemu-system-x86 qemu-utils ovmf"

if [ "$reset" -eq 1 ]; then
    rm -rf "$STATE"
    echo "Removed $STATE"
fi

if [ "$mode" != disk ]; then
    if [ -z "$iso" ]; then
        iso="$(ls -1t "$ROOT"/out/"$DISTRO_ID"-*-"$desktop"-amd64.iso 2>/dev/null | head -n1 || true)"
        [ -n "$iso" ] || die "No ISO found. Build one with tools/build-iso.sh --desktop $desktop or pass --iso FILE."
    fi
    [ -r "$iso" ] || die "Cannot read ISO: $iso"
fi

if [ "$mode" = disk ]; then
    [ -e "$DISK" ] || die "No test disk. Install first: tools/test-iso.sh --desktop $desktop --install"
    installed_fw="$(cat "$FW_FILE" 2>/dev/null || echo uefi)"
    if [ -n "$firmware" ] && [ "$firmware" != "$installed_fw" ]; then
        echo "Warning: disk was installed with $installed_fw, booting with $firmware may fail." >&2
    fi
    firmware="${firmware:-$installed_fw}"
fi
firmware="${firmware:-uefi}"

args=(
    # No comma in the window title: QEMU parses -name as a comma-separated
    # option list, and a literal comma there is taken as another parameter.
    -name "$DISTRO_ID $desktop test - $mode - $firmware"
    -m "$mem" -smp 2
    -device virtio-vga
    -nic user,model=virtio-net-pci
    -usb -device usb-tablet
)

if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    args+=(-enable-kvm -cpu host)
elif [ ! -e /dev/kvm ]; then
    echo "Warning: /dev/kvm is missing, running without acceleration (slow)." >&2
    echo "         Load the module: sudo modprobe kvm_intel   (AMD: kvm_amd)" >&2
    echo "         Blacklisted in /etc/modprobe.d/ (e.g. alongside VirtualBox)? That only" >&2
    echo "         blocks auto-loading; modprobe still works. Unload again with" >&2
    echo "         sudo modprobe -r kvm_intel kvm. If modprobe fails, enable" >&2
    echo "         virtualization (VT-x/AMD-V) in the BIOS/UEFI." >&2
else
    echo "Warning: no permission on /dev/kvm, running without acceleration (slow)." >&2
    echo "         Fix: sudo adduser \$USER kvm, then log out and back in." >&2
fi

tmp_vars=""
cleanup() { if [ -n "$tmp_vars" ]; then rm -f "$tmp_vars"; fi; }
trap cleanup EXIT

if [ "$firmware" = uefi ]; then
    [ -r "$OVMF_CODE" ] || die "OVMF not found. Install: sudo apt install ovmf"
    if [ "$mode" = live ]; then
        # Throwaway variables so live tests don't touch the install's boot entries.
        tmp_vars="$(mktemp --suffix=.fd)"
        cp "$OVMF_VARS" "$tmp_vars"
        vars="$tmp_vars"
    else
        mkdir -p "$STATE"
        [ -e "$VARS" ] || cp "$OVMF_VARS" "$VARS"
        vars="$VARS"
    fi
    args+=(
        -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
        -drive "if=pflash,format=raw,file=$vars"
    )
fi

case "$mode" in
    live)
        args+=(-cdrom "$iso" -boot d)
        ;;
    install)
        command -v qemu-img >/dev/null || die "Install qemu-utils: sudo apt install qemu-utils"
        mkdir -p "$STATE"
        if [ ! -e "$DISK" ]; then
            qemu-img create -q -f qcow2 "$DISK" "$size"
            echo "Created $DISK ($size)"
        fi
        echo "$firmware" > "$FW_FILE"
        # Boot the ISO once; rebooting from inside the VM starts the installed disk.
        args+=(-drive "file=$DISK,if=virtio" -cdrom "$iso" -boot once=d)
        ;;
    disk)
        args+=(-drive "file=$DISK,if=virtio" -boot c)
        ;;
esac

echo "Booting: mode=$mode firmware=$firmware${iso:+ iso=$(basename "$iso")}"
# Not exec: the EXIT trap must still remove temporary UEFI variables.
qemu-system-x86_64 "${args[@]}"
