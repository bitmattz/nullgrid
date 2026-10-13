# NULLGRID build entry points. Everything Arch-specific runs in the builder container.
#   make iso        build out/nullgrid-YYYY.MM.DD-x86_64.iso
#   make run        boot it in QEMU (UEFI). Variants: run-bios, run-gl
#   make test-boot  headless boot + checks over serial (runs in Docker; no host QEMU needed)

BUILDER  ?= nullgrid-builder
WORKVOL  ?= nullgrid-work
KVM      := $(if $(wildcard /dev/kvm),--device /dev/kvm,)
DOCKER    = docker run --rm $(DOCKER_TTY) -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) \
            -v $(CURDIR):/src -v $(WORKVOL):/work $(BUILDER)
DOCKER_TTY = $(if $(shell [ -t 0 ] && echo y),-it,)

.PHONY: help builder repo iso run run-bios run-gl test-boot test-boot-bios shell check-host clean distclean

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

test-boot:
	docker run --rm -i $(KVM) -e PYTHONUNBUFFERED=1 -e BOOT_TIMEOUT -v $(CURDIR):/src $(BUILDER) python3 /src/tests/boot_smoke.py

test-boot-bios:
	docker run --rm -i $(KVM) -e PYTHONUNBUFFERED=1 -e BOOT_TIMEOUT -v $(CURDIR):/src $(BUILDER) python3 /src/tests/boot_smoke.py --bios

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
