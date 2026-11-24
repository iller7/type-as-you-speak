FROM fedora:45@sha256:a7d72ba2745b100a3351087472e5ee7b2450af7cf331e7673007e3817612839c AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 QT_QPA_PLATFORM=offscreen
RUN dnf install -y python3-devel python3-pip rpm-build findutils gcc \
    desktop-file-utils appstream && dnf clean all
RUN python3 -m venv /tools
ENV PATH="/tools/bin:${PATH}"
RUN pip install --no-cache-dir uv==0.13.9
ENV UV_PYTHON=/usr/bin/python3 UV_PYTHON_DOWNLOADS=never
WORKDIR /work
COPY . .
RUN python3 -c 'import subprocess; deps=subprocess.check_output(["rpmspec", "--query", "--buildrequires", "packaging/fedora/type-as-you-speak.spec"], text=True).splitlines(); subprocess.run(["dnf", "install", "-y", *deps], check=True)'
RUN uv sync --locked --python /usr/bin/python3 --extra gui
ENV PATH="/work/.venv/bin:/tools/bin:${PATH}"
RUN uv run --locked pytest && uv run --locked python -m build --no-isolation && bash scripts/prepare-wheelhouse.sh
RUN mkdir -p /root/rpmbuild/SOURCES && cp dist/*.tar.gz /root/rpmbuild/SOURCES/ && \
    tar -czf /root/rpmbuild/SOURCES/wheelhouse.tar.gz -C dist/wheelhouse .
RUN rpmbuild -ba packaging/fedora/type-as-you-speak.spec
FROM fedora:45@sha256:a7d72ba2745b100a3351087472e5ee7b2450af7cf331e7673007e3817612839c AS smoke
ENV QT_QPA_PLATFORM=offscreen
COPY --from=build /root/rpmbuild/RPMS/ /packages/
RUN dnf install -y /packages/*/*.rpm && tays --version && tays --help && \
    /usr/bin/python3 -c 'import sys; sys.path.insert(0,"/opt/type-as-you-speak/pydeps"); import numpy, onnxruntime, faster_whisper; from PySide6.QtWidgets import QApplication; app=QApplication([])'
FROM build AS verify
COPY --from=smoke /opt/type-as-you-speak/pydeps /installed-pydeps
RUN python scripts/audit.py /installed-pydeps && \
    mkdir /out && cp /root/rpmbuild/RPMS/*/*.rpm /root/rpmbuild/SRPMS/*.rpm /out/
FROM scratch AS artifacts
COPY --from=verify /out/ /
