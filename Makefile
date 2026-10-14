# NULLGRID build entry points. Everything Arch-specific runs in the builder container.
#   make iso        build out/nullgrid-YYYY.MM.DD-x86_64.iso
#   make run        boot it in QEMU (UEFI). Variants: run-bios, run-gl
#   make test       unit + snapshot tests of nullgrid, nullgrid-sfx, nullgrid-dash, the installer (in Docker)
#   make sounds     generate the sound packs into out/sounds (nullgrid sound test plays them)
#   make test-shell the desktop shell + GTK/Qt apps in a headless Sway: QML errors, IPC, live restyle
#   make splash     preview the Plymouth boot splash (X11 renderer, Docker) -> out/screens/splash-*.png
#   make test-boot  headless boot + checks over serial (runs in Docker; no host QEMU needed)
#   make test-install  install the ISO to a virtual disk, boot it (UEFI + BIOS), check it (ENCRYPT=1: LUKS)

BUILDER  ?= nullgrid-builder
WORKVOL  ?= nullgrid-work
KVM      := $(if $(wildcard /dev/kvm),--device /dev/kvm,)
DOCKER    = docker run --rm $(DOCKER_TTY) -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
            -v $(CURDIR):/src -v $(WORKVOL):/work $(BUILDER)
DOCKER_TTY = $(if $(shell [ -t 0 ] && echo y),-it,)

.PHONY: help builder repo iso run run-bios run-gl test sounds test-shell splash test-boot test-boot-bios test-install shell check-host clean distclean

help:
	@sed -n 's/^#   //p' Makefile

builder:
	docker build -t $(BUILDER) build/

repo: builder
	$(DOCKER) /src/build/build-packages.sh

# mkarchiso needs loop devices and chroots, hence --privileged.
iso: repo
	docker run --rm --privileged -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
		-v $(CURDIR):/src -v $(WORKVOL):/work $(BUILDER) /src/build/build-iso.sh

run:
	build/run-vm.sh

run-bios:
	build/run-vm.sh --bios

run-gl:
	build/run-vm.sh --gl

# Regenerate snapshots after an intended template change: make test NULLGRID_UPDATE_SNAPSHOTS=1
test: builder
	docker run --rm $(DOCKER_TTY) -e PYTHONDONTWRITEBYTECODE=1 -e NULLGRID_UPDATE_SNAPSHOTS \
		--user $(shell id -u):$(shell id -g) -v $(CURDIR):/src $(BUILDER) \
		python -m pytest -q -p no:cacheprovider /src/tests/nullgrid /src/tests/nullgrid_sfx /src/tests/nullgrid_dash \
		/src/tests/nullgrid_install $(PYTEST_ARGS)

sounds: builder
	docker run --rm --user $(shell id -u):$(shell id -g) -v $(CURDIR):/src $(BUILDER) \
		python /src/assets/sounds/generate.py --out /src/out/sounds

test-shell: builder
	docker run --rm $(DOCKER_TTY) -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
		-v $(CURDIR):/src $(BUILDER) /src/tests/shell_smoke.sh

splash: builder
	docker run --rm -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) -v $(CURDIR):/src $(BUILDER) \
		/src/tests/splash_preview.sh

test-boot:
	docker run --rm -i $(KVM) -e PYTHONUNBUFFERED=1 -e BOOT_TIMEOUT -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
		-v $(CURDIR):/src $(BUILDER) python3 /src/tests/boot_smoke.py

test-boot-bios:
	docker run --rm -i $(KVM) -e PYTHONUNBUFFERED=1 -e BOOT_TIMEOUT -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
		-v $(CURDIR):/src $(BUILDER) python3 /src/tests/boot_smoke.py --bios

test-install:
	docker run --rm -i $(KVM) -e PYTHONUNBUFFERED=1 -e BOOT_TIMEOUT -e INSTALL_TIMEOUT -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
		-v $(CURDIR):/src $(BUILDER) python3 /src/tests/install_smoke.py $(if $(ENCRYPT),--encrypt,)

shell: builder
	docker run --rm -it --privileged -v $(CURDIR):/src -v $(WORKVOL):/work $(BUILDER) bash

check-host:
	@command -v docker >/dev/null && echo "ok   docker" || echo "MISSING docker (required)"
	@command -v qemu-system-x86_64 >/dev/null && echo "ok   qemu" || echo "missing qemu (needed for 'make run'; 'make test-boot' works without it)"
	@ls /usr/share/OVMF/OVMF_CODE*.fd /usr/share/edk2/x64/OVMF_CODE*.fd >/dev/null 2>&1 && echo "ok   OVMF" || echo "missing OVMF (needed for UEFI 'make run')"
	@[ -w /dev/kvm ] && echo "ok   /dev/kvm" || echo "missing /dev/kvm access (VMs will be slow)"
	@df -h --output=avail $(CURDIR) | tail -1 | xargs echo "disk free here:"

clean:
	rm -rf out

distclean: clean
	-docker volume rm $(WORKVOL)
