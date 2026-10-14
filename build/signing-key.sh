#!/usr/bin/env bash
# The NULLGRID package signing key (`make sign-key`). Runs in the builder container.
#
# The private key lives on the host only, in $NULLGRID_SIGNING (default
# ~/.local/share/nullgrid-signing), mounted here at /signing. It is never committed: keep an
# offline backup (see docs/RELEASING.md). This script creates the key if there is none, then
# exports the public half into pkg/nullgrid-keyring/, which ships it to every NULLGRID system.
set -euo pipefail

export GNUPGHOME=/signing/gnupg
keyring=/src/pkg/nullgrid-keyring
uid="NULLGRID packages (https://github.com/bitmattz/nullgrid)"

mkdir -p -m 700 "$GNUPGHOME"
if ! gpg --batch --list-secret-keys "$uid" >/dev/null 2>&1; then
    echo ":: creating the signing key: $uid"
    # ed25519, no passphrase (signing runs unattended), no expiry (an expired key would silently
    # stop updates on every installed system; revoke it instead if it ever leaks)
    gpg --batch --pinentry-mode loopback --passphrase '' \
        --quick-generate-key "$uid" ed25519 sign never
fi
fpr=$(gpg --batch --with-colons --list-secret-keys "$uid" | awk -F: '$1 == "fpr" { print $10; exit }')
echo ":: signing key $fpr"
echo "$fpr" > /signing/fingerprint

# pacman-key --populate nullgrid reads these (the same layout as archlinux-keyring)
gpg --batch --export "$fpr" > "$keyring/nullgrid.gpg"
echo "$fpr:4:" > "$keyring/nullgrid-trusted"
: > "$keyring/nullgrid-revoked"
echo ":: public key exported to pkg/nullgrid-keyring/ (commit it)"
