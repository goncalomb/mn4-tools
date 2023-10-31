#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

if ! grep -qxF "dtoverlay=dwc2" /boot/config.txt; then
    echo "adding 'dtoverlay=dwc2' to '/boot/config.txt'..."
    echo dtoverlay=dwc2 | sudo tee -a /boot/config.txt >/dev/null
    touch /tmp/.reboot
    echo "rebooting in 10 seconds..."
    sleep 10
    sudo reboot
    exit
fi

[ -f /tmp/.reboot ] && echo "reboot required to continue" && exit 1

if ! command -v socat >/dev/null; then
    sudo apt-get -y install socat
fi
