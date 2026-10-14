# Arch Linux build environment for NULLGRID.
# The host may be any distro with Docker; mkarchiso and makepkg run in here.
# It also carries QEMU + OVMF so `make test-boot` works on hosts without them.
FROM archlinux:latest

RUN pacman -Syu --noconfirm --needed \
        archiso base-devel git sudo pacman-contrib \
        python python-jinja python-tomlkit python-pytest python-textual python-psutil \
        python-build python-installer python-flit-core python-numpy lua \
        qemu-base qemu-hw-display-virtio-vga qemu-hw-display-virtio-gpu edk2-ovmf \
        quickshell sway swaybg grim librsvg hyprlock dbus libnotify ttf-jetbrains-mono \
        adw-gtk-theme adwaita-icon-theme qt6ct dconf gsettings-desktop-schemas thunar zathura \
        zathura-pdf-mupdf greetd-tuigreet \
    && pacman -Scc --noconfirm

# makepkg refuses to run as root, so packages are built as this user.
RUN useradd -m builder \
    && echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder

WORKDIR /src
