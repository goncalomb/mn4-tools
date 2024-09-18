#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

# patches f_serial.c to set 'bInterfaceSubClass = USB_SUBCLASS_VENDOR_SPEC'
# to match the expected value used by Android Open Accessory (AOA)

K_RELEASE=$(uname -r)
K_MODULES="/lib/modules/$K_RELEASE"
K_MODULES_OUR="$K_MODULES/usb_f_serial_patched.ko"

if [ ! -f "$K_MODULES_OUR" ]; then
    # based on:
    # https://github.com/RPi-Distro/rpi-source/blob/master/rpi-source
    # https://github.com/RPi-Distro/rpi-source/issues/25

    K_HASH=$(zcat /usr/share/doc/linux-image-$K_RELEASE/changelog.Debian.gz | grep -F -m1 "Linux commit" | grep -Pio "[0-9a-f]{40}" || true)
    [ -z "$K_HASH" ] && echo "failed to find kernel commit hash" && exit 1

    K_SOURCE="linux-source/linux-$K_HASH"
    if [ ! -f "$K_SOURCE/Kconfig" ]; then
        mkdir -p "$K_SOURCE"
        (
            cd "$K_SOURCE"
            apt-get -y install build-essential flex bison bc
            echo "getting kernel source..."
            git init -q
            git remote add origin https://github.com/raspberrypi/linux.git || true
            git fetch --depth 1 origin "$K_HASH"
            # too slow, we'll use some plumbing commands
            # git -c advice.detachedHead=false checkout FETCH_HEAD
            echo "unpacking kernel source..."
            git read-tree FETCH_HEAD && git checkout-index -a
        )
    fi

    (
        cd "$K_SOURCE"
        echo "building kernel module..."
        # patch
        sed -i "s/bInterfaceSubClass.*=.*0/bInterfaceSubClass = USB_SUBCLASS_VENDOR_SPEC/g" drivers/usb/gadget/function/f_serial.c
        # build
        cp "/usr/src/linux-headers-$K_RELEASE/Module.symvers" .
        [ -f .config ] || yes "" | make oldconfig || true
        make modules_prepare
        make M=drivers/usb/gadget/function modules
        # make drivers/usb/gadget/function/usb_f_serial.ko
        cp drivers/usb/gadget/function/usb_f_serial.ko "$K_MODULES_OUR"
    )
fi

# our patched module
file "$K_MODULES_OUR"

# disable original module and load patched version
echo "enabling kernel module..."
depmod -a
rmmod usb_f_serial || true
modprobe -v usb_f_serial_patched
