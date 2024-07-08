FROM ghcr.io/srl-labs/containerlab/clab-devcontainer:0.55.1

COPY --chmod=755 . /netobs

WORKDIR /netobs

RUN pip install --upgrade pip && \
    pip install .