# Máquina nova para provar a instalação automática do motor de voz: Ubuntu 24.04, sem PortAudio nem tocador de áudio.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 curl ca-certificates git less \
    && rm -rf /var/lib/apt/lists/*

# Usuário comum, sem sudo.
RUN useradd --create-home --shell /bin/bash pessoa
USER pessoa
WORKDIR /home/pessoa
ENV PATH="/home/pessoa/.local/bin:${PATH}"

# uv pelo instalador oficial (instala em ~/.local/bin).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Claude Code pelo instalador oficial (nativo), com versão fixa.
ARG CLAUDE_VERSION=2.1.312
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_VERSION}"

CMD ["bash"]
