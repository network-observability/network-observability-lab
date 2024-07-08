FROM ghcr.io/srl-labs/containerlab/clab-devcontainer:0.55.1

USER vscode

WORKDIR /netobs

COPY . /netobs

RUN pip install --upgrade pip && \
    pip install .