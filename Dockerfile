FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ripgrep ca-certificates git curl && \
    rm -rf /var/lib/apt/lists/*

RUN update-ca-certificates

RUN pip3 install --no-cache-dir --upgrade pip

RUN curl -L https://sh.rustup.rs -sSf | sh -s -- -y && \
    /root/.cargo/bin/cargo install toml-cli

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /work

COPY bin/ bin/
COPY configs/ configs/
COPY overrides/ overrides/
COPY tools/ tools/
COPY data/ data/
COPY .gitignore README.md ./

ENTRYPOINT ["/bin/bash"]