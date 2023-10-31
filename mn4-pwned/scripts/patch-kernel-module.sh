#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

K_RELEASE=$(uname -r)
K_MODULES="/lib/modules/$K_RELEASE"
K_MODULES_OUR="$K_MODULES/usb_f_serial_patched.ko"

if [ ! -f "$K_MODULES_OUR" ]; then
    K_SOURCE=$(find /usr/src/ -maxdepth 1 -name "linux-source-*.tar.*")
    if [ -z "$K_SOURCE" ]; then
        echo "getting kernel source..."
        apt-get -y install build-essential linux-source
        K_SOURCE=$(find /usr/src/ -maxdepth 1 -name "linux-source-*.tar.*")
    fi

    if [ ! -d linux-source ]; then
        echo "extracting kernel source..."
        tar -xf "$K_SOURCE"
        mv linux-source-* linux-source
    fi

    (
        echo "building kernel module..."
        cd linux-source
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
