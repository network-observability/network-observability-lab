FROM ghcr.io/srl-labs/containerlab/clab-devcontainer:0.55.1

COPY . /netobs

WORKDIR /netobs

RUN chmod -R 777 .

RUN pip install --upgrade pip && \
    pip install .