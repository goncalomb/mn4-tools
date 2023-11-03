#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

rm -rf tmp

sudo ./scripts/ctrl-gadget.sh remove
echo "gadget removed"
