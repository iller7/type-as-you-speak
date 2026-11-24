FROM archlinux:base@sha256:375a401bb3c6376b37f40b6dfa25067db37ec78d0b7af67ae6315f43a0184a9d AS build
RUN pacman -Syu --noconfirm --needed base-devel python-build python-installer python-setuptools python-wheel && \
    useradd --create-home builder
WORKDIR /source
COPY . .
# Exercise this checkout rather than downloading and retesting an older release tag.
RUN version=$(sed -n 's/^pkgver=//p' packaging/aur/PKGBUILD.in) && \
    mkdir -p /home/builder/package && \
    tar -czf "/home/builder/package/type-as-you-speak-${version}.tar.gz" --transform "s,^,type-as-you-speak-${version}/," . && \
    cp packaging/aur/PKGBUILD.in /home/builder/package/PKGBUILD && \
    cd /home/builder/package && \
    sed -i 's|^source=.*|source=("$pkgname-$pkgver.tar.gz")|' PKGBUILD && \
    hash=$(sha256sum "type-as-you-speak-${version}.tar.gz" | cut -d' ' -f1) && \
    sed -i "s/^sha256sums=.*/sha256sums=('$hash')/" PKGBUILD && \
    chown -R builder:builder /home/builder/package
USER builder
WORKDIR /home/builder/package
# Inference dependencies may be AUR packages; this job checks packaging, not desktop operation.
RUN makepkg --nodeps --cleanbuild --noconfirm && \
    tar -tf type-as-you-speak-*.pkg.tar.zst | grep -q usr/bin/tays
