FROM fedora:44@sha256:15da97ed9aa94dd3d92c3925eb89520f6c80e07ea7ee24cba848d1f8b6912b3e AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 QT_QPA_PLATFORM=offscreen
RUN dnf install -y python3-devel python3-pip rpm-build findutils gcc \
    fontconfig mesa-libEGL libglvnd-opengl libglvnd-glx libxkbcommon-x11 xcb-util-cursor desktop-file-utils appstream && dnf clean all
RUN python3 -m venv /tools
ENV PATH="/tools/bin:${PATH}"
RUN pip install --no-cache-dir uv==0.13.9
ENV UV_PYTHON=/usr/bin/python3 UV_PYTHON_DOWNLOADS=never
WORKDIR /work
COPY . .
RUN uv sync --locked --python /usr/bin/python3 --extra gui
ENV PATH="/work/.venv/bin:/tools/bin:${PATH}"
RUN uv run --locked pytest && uv run --locked python -m build --no-isolation && bash scripts/prepare-wheelhouse.sh
RUN mkdir -p /root/rpmbuild/SOURCES && cp dist/*.tar.gz /root/rpmbuild/SOURCES/ && \
    tar -czf /root/rpmbuild/SOURCES/wheelhouse.tar.gz -C dist/wheelhouse .
RUN rpmbuild -ba packaging/fedora/type-as-you-speak.spec
RUN dnf install -y /root/rpmbuild/RPMS/*/*.rpm && tays --version && tays --help && \
    python scripts/audit.py /opt/type-as-you-speak/pydeps && \
    /usr/bin/python3 -c 'import sys; sys.path.insert(0,"/opt/type-as-you-speak/pydeps"); from PySide6.QtWidgets import QApplication; app=QApplication([])' && \
    mkdir /out && cp /root/rpmbuild/RPMS/*/*.rpm /root/rpmbuild/SRPMS/*.rpm /out/
FROM scratch AS artifacts
COPY --from=build /out/ /
