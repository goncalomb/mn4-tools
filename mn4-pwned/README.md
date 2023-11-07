# Media Nav 4 Pwned (mn4-pwned)

This directory contains scripts capable of pwning the Media Nav 4 (target device) with recent firmware versions.

It uses a bespoke implementation of a communication protocol used to send/receive files to/from the target device. Officially, this protocol is used to update the navigation maps on the device but it can also be used to update arbitrary files.

This project does not contain any proprietary code. All code is original.

The procedure was created by reverse engineering the original firmware.

## Overview

The procedure is something like this:

* Setup a Raspberry Pi Zero 2 W as a USB Gadget with specific parameters that trick the target device into thinking that it is connected to an Android device using [Android Open Accessory (AOA)](https://source.android.com/docs/core/interaction/accessories/protocol);
* Exploit the navigation maps update feature of the target device to send arbitrary files;
* Send designed payload to the device;
* Trigger the payload (it runs as root);
* Profit;

## Scripts

* `./setup.sh`: setups the Raspberry Pi, downloads dependencies, patches the kernel and creates the USB Gadget;
* `./payload-send.sh [payload-file]`: sends the payload to the device
* `./payload-clear.sh`: clears the payload from the device
* `./cleanup.sh`: removes the USB Gadget

### Other

You don't need to call these scripts directly, they are called by the primary scripts.

* `./scripts/install-dependencies.sh`: installs dependencies
* `./scripts/patch-kernel-module.sh`: creates patched kernel module (required for AOA)
* `./scripts/ctrl-gadget.sh`: controls the USB Gadget
* `./scripts/ctrl-proto.py`: send commands to the target device (CAUTION: you could destroy your device with this script, e.g. delete system files)

## Usage

Requirements: Raspberry Pi Zero 2 W (other versions might work but not tested), GNU/Linux system recommended.

Read all the instructions before starting so that you have an idea of what is required.

### Setup

* Setup a microSD card with a fresh Raspberry Pi OS installation;
    * I suggest just using the [official imager](https://www.raspberrypi.com/software/).
    * Tested with Raspberry Pi OS Lite (32-bit) (2023-10-10).
* Enable SSH, set password and configure wireless network;
    * You can do all this using the official imager or other methods.
* Get the `mn4-pwned` code;
    * If you are on a system that supports ext4, you can just copy the code to the microSD card at `/home/pi` (rootfs).
    * If not, just wait for later.
* Boot the Raspberry Pi;
* Connect using SSH;
    * Get the `mn4-pwned` code, if you didn't already, use `git`, `wget` or something else.
* At this point you should have the `mn4-pwned` directory, `cd` in into it;
* Run `./setup.sh`, the first time it should ask to reboot after setting `dtoverlay=dwc2`;
* Reboot and `cd` back into `mn4-pwned`.
* Run `./setup.sh` again, this time it should download the Linux kernel sources and compile a patched module. This can take ~9min.
* After all that you should see the message "gadget created";
* Power off the Raspberry Pi;

### Pwning

This involves connecting the Raspberry Pi to the target device using a standard USB Micro-B to Type-A cable using the OTG port on the RPi. The RPi can be powered from the OTG port. While connected to the target device you need to have SSH access to the RPi, plan the wireless setup accordingly.

* Connect the Raspberry Pi (OTG port) to the target device;
* On the target device select "Navigation" > "Menu" > "Map Update" > "Options" > "Update with Phone";
* You should see the message "Phone not connected!";
* Connect to the Raspberry Pi using SSH;
* `cd` into `mn4-pwned`;
* Run `./setup.sh`, after a few seconds you will see the message "gadget created";
* On the target device, you should see "Phone connected! Waiting for maps to be transferred.";
* Run `./payload-send.sh` to create the backdoor and deliver the payload;
* Optionally run `./cleanup.sh` to close the connection;
* Click "Exit update" on the target device;

To run the payload just go back into "Update with Phone". For a few seconds, you should see the message "PWNED!" showing the root user id.

Other payloads (bash scripts) can be delivered as an argument to `./payload-send.sh`. To remove the backdoor and payload use `./payload-clear.sh`.
