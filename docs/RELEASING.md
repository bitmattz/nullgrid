# Releasing

How a NULLGRID release is cut (1.0.0 was the first).

## 1. Version

The release version is in `VERSION` at the repo root. Every NULLGRID package (`pkg/*/PKGBUILD`
`pkgver`, except `nullgrid-fonts`, which versions the bundled fonts), every tool's `__version__`
and `os-release` (`VERSION`, `VERSION_ID`) must carry it; `tests/nullgrid/test_versions.py`
fails otherwise. The ISO is named after it: `out/nullgrid-<VERSION>-x86_64.iso`.

Bump all of them, then update the snapshots (the wallpaper prints the version):

```sh
make test NULLGRID_UPDATE_SNAPSHOTS=1    # review: only "version" lines should change
```

## 2. Build and test the release ISO

```sh
make iso
make test            # unit + snapshot tests
make test-shell      # shell + GTK/Qt apps in a headless Sway
make test-boot       # the live ISO
make test-install    # install to a VM disk, boot it UEFI + BIOS (also: ENCRYPT=1)
make perf            # idle memory/CPU; update docs/PERFORMANCE.md if the numbers moved
```

All must print `PASS`. Look at the screenshots in `out/screens/` too.

## 3. Notes

- Add the version to `CHANGELOG.md`.
- Write `docs/releases/v<VERSION>.md`: download and verify, what's new, measured numbers, how it
  was tested, known limitations. It becomes the GitHub release text.

Commit, push.

## 4. Publish

Needs the GitHub CLI (`gh auth login` once).

```sh
v=$(cat VERSION)
cd out && sha256sum nullgrid-$v-x86_64.iso > SHA256SUMS && cd ..
git tag -a v$v -m "NULLGRID $v" && git push origin v$v
gh release create v$v --title "NULLGRID OS $v" --notes-file docs/releases/v$v.md \
    out/nullgrid-$v-x86_64.iso out/SHA256SUMS
```

GitHub takes files up to 2 GiB per release asset; the ISO is ~1.9 GB. If it grows past that,
split it (`split -b 1900M`) and document joining it, or trim the package list.

## 5. The update repository

Installed systems update from the `[nullgrid]` repository: the GitHub release `repo` (a
pre-release, so the latest version release stays "Latest"). Every publish replaces it with the
current packages, signed.

```sh
make sign-key        # once per machine that publishes: creates (or re-exports) the key
make publish-repo    # make repo, sign everything + the database, upload to the 'repo' release
make test-upgrade    # optional before upload: 1.0.0 ISO -> keyring -> pacman -Syu from out/publish
```

`make publish-repo` builds and signs into `out/publish/` first (`build/sign-repo.sh`), then
uploads (`build/publish-repo.sh`, needs `gh`). To test before uploading, run the signing step
alone (see the Makefile) and `make test-upgrade`.

**Only released versions go in** (the owner's rule): bump `VERSION` first, or pacman sees nothing
new. Packaging-only fixes bump `pkgrel` of that package.

### The signing key

- Private key: `~/.local/share/nullgrid-signing/` on the publishing machine (no passphrase, mode
  700), **never in the repo**. Back it up offline: without it, no more updates can be signed,
  and every system would need a new keyring package installed by hand.
- Public key: `pkg/nullgrid-keyring/` (committed), shipped by the `nullgrid-keyring` package,
  fingerprint `3494FF826CBF4E4AB1E83049FD658A9D368049E7`.
- If it leaks: create a new key, put the old fingerprint in `nullgrid-revoked`, ship the new
  `nullgrid-keyring` (bump its date version) signed with the old key one last time, announce it.

```sh
# backup (keep it somewhere safe and offline)
tar -C ~/.local/share -czf nullgrid-signing-backup.tar.gz nullgrid-signing
```
