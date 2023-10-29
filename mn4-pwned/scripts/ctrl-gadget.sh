#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

G_NAME="mn4gadget"

modprobe libcomposite
cd /sys/kernel/config/usb_gadget

cmd_create() {
    mkdir "$G_NAME"
    cd "$G_NAME"

    echo 0x18d1 >idVendor
    echo 0x2d00 >idProduct

    mkdir configs/c.1
    mkdir functions/gser.usb0
    ln -s functions/gser.usb0 configs/c.1/

    ls /sys/class/udc >UDC
}

cmd_remove() {
    cd "$G_NAME"
    echo "" >UDC
    rm configs/c.1/gser.usb0
    rmdir functions/gser.usb0
    rmdir configs/c.1
    cd ..
    rmdir "$G_NAME"
}

cmd_reset() {
    cd "$G_NAME"
    echo "" >UDC
    ls /sys/class/udc >UDC
}

cmd_port() {
    NUM=$(cat "$G_NAME/functions/gser.usb0/port_num")
    echo "/dev/ttyGS$NUM"
}

case "${1:-}" in
    create) cmd_create ;;
    remove) cmd_remove ;;
    reset) cmd_reset ;;
    port) cmd_port ;;
    *) echo "missing command (create/remove/reset/port)" >&2 && exit 1 ;;
esac
