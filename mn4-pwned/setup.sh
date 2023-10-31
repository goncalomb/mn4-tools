#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

./scripts/install-dependencies.sh
sudo ./scripts/patch-kernel-module.sh
