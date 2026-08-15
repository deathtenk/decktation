FROM ghcr.io/steamdeckhomebrew/holo-base:latest

ARG YDOTOOL_COMMIT=57ba7d0af525e82da2de0e275d169477f293b197

RUN pacman -Sydd --noconfirm --dbpath /var/lib/pacman \
        git portaudio python-pip

RUN mkdir -p /backend
COPY entrypoint.sh /backend/entrypoint.sh
RUN chmod 755 /backend/entrypoint.sh

WORKDIR /runtime-build

COPY runtime/pyproject.toml runtime/uv.lock runtime/decktation-runtime.spec runtime/runtime_entry.py /runtime-build/runtime/

RUN python3 -m venv /runtime-build/tooling-venv \
    && /runtime-build/tooling-venv/bin/python -m pip install --no-cache-dir uv \
    && cd /runtime-build/runtime \
    && /runtime-build/tooling-venv/bin/uv sync --locked --python 3.11 --no-install-project \
    && /runtime-build/tooling-venv/bin/uv pip install --python .venv/bin/python pyinstaller

COPY runtime/src /runtime-build/runtime/src
COPY defaults /runtime-build/defaults
COPY plugin.json /runtime-build/plugin.json

RUN git init /ydotool-src \
    && git -C /ydotool-src remote add origin https://github.com/ReimuNotMoe/ydotool.git \
    && git -C /ydotool-src fetch --depth 1 origin "${YDOTOOL_COMMIT}" \
    && git -C /ydotool-src checkout --detach FETCH_HEAD \
    && mkdir -p /ydotool-build \
    && cc -std=c99 -O2 -D_DEFAULT_SOURCE -DVERSION='"v1.0.4"' \
        -o /ydotool-build/ydotoold /ydotool-src/Daemon/ydotoold.c \
    && cc -std=c99 -O2 -D_DEFAULT_SOURCE -DVERSION='"v1.0.4"' \
        -I/ydotool-src/Client \
        -o /ydotool-build/ydotool \
        /ydotool-src/Client/ydotool.c \
        /ydotool-src/Client/tool_click.c \
        /ydotool-src/Client/tool_mousemove.c \
        /ydotool-src/Client/tool_type.c \
        /ydotool-src/Client/tool_key.c

RUN cd /runtime-build/runtime \
    && YDOTOOL_BIN=/ydotool-build/ydotool \
       YDOTOOLD_BIN=/ydotool-build/ydotoold \
       PORTAUDIO_LIB=/usr/lib/libportaudio.so.2 \
       .venv/bin/pyinstaller decktation-runtime.spec

ENTRYPOINT ["/backend/entrypoint.sh"]
