FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

RUN echo "deb [trusted=yes] https://netdevops.fury.site/apt/ /" | \
    tee -a /etc/apt/sources.list.d/netdevops.list

# install containerlab and tools
RUN apt update && \
    apt install -y --no-install-recommends containerlab \
    btop \
    gh \
    iputils-ping \
    tcpdump \
    iproute2 \
    qemu-kvm \
    dnsutils \
    telnet

# Install gNMIc
RUN bash -c "$(curl -sL https://get-gnmic.openconfig.net)"

# Add empty docker config files to avoid clab warnings for root user
RUN mkdir -p /root/.docker && echo "{}" > /root/.docker/config.json

# Maintain SSH_AUTH_SOCK env var when using sudo
RUN mkdir -p /etc/sudoers.d && echo 'Defaults env_keep += "SSH_AUTH_SOCK"' > /etc/sudoers.d/ssh_auth_sock

# vscode user is created in the MS devcontainer image
USER vscode

ENV PATH="$PATH:/home/vscode/.local/bin"

# Create ssh key for vscode user to enable passwordless ssh to devices
RUN ssh-keygen -t ecdsa -b 256 -N "" -f ~/.ssh/id_ecdsa && \
    mkdir -p /home/vscode/.docker && \
    echo "{}" > /home/vscode/.docker/config.json

COPY --chown=vscode:vscode --chmod=700 . /netobs

RUN pip install --upgrade pip && \
    cd /netobs && \
    pip install . && \
    rm -r /netobs/*
