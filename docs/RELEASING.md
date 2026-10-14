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

## Updates (not yet)

Installed systems update Arch packages with `pacman -Syu`, but NULLGRID's own packages only
come with a new ISO. The plan for later (see DECISIONS.md, "Updates"): a signed `[nullgrid]`
pacman repository on a GitHub release, a `nullgrid-keyring` package, `make publish-repo`, a
pacman hook that regenerates users' configs, and `nullgrid update`.
