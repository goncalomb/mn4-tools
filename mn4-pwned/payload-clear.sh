#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

mkdir -p tmp

echo "resetting gadget..."
sudo ./scripts/ctrl-gadget.sh reset
sleep 2

echo "downloading 'main-ulc.xs'..."
rm -f tmp/main-ulc.xs
./scripts/ctrl-proto.py pull yellowtool/src/main-ulc.xs tmp/main-ulc.xs

if grep -qF "// mn4-pwned-v0" tmp/main-ulc.xs; then
    sed -i '/\/\/ mn4-pwned-v0/d' tmp/main-ulc.xs

    echo "uploading clean 'main-ulc.xs'..."
    ./scripts/ctrl-proto.py push tmp/main-ulc.xs yellowtool/src/main-ulc.xs

    SHA1=$(sha1sum tmp/main-ulc.xs | head -c40)
    echo "file hash = $SHA1"

    echo "removing payload..."
    ./scripts/ctrl-proto.py delete yellowtool/pwn.sh
else
    echo "not pwned, nothing to do"
fi
