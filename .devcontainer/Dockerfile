FROM ghcr.io/srl-labs/containerlab/clab-devcontainer:0.55.1

# USER vscode

# WORKDIR /netobs

# COPY --chown=vscode:vscode --chmod=700 . /netobs
# # COPY . /netobs

# RUN pip install --upgrade pip && \
#     pip install . && \
#     cp example.env .env && \
#     netobs docker build

COPY ./build/cEOS64-lab-4.32.0.1F.tar cEOS64-lab-4.32.0.1F.tar

# RUN docker load -i cEOS64-lab-4.32.0.1F.tar
# RUN docker import cEOS64-lab-4.32.0.1F.tar ceos:image && \
#     rm cEOS64-lab-4.32.0.1F.tar
