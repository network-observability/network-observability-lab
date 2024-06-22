ARG PYTHON_VER=3.10

FROM python:${PYTHON_VER}

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y git libpcap-dev tshark inetutils-ping bpfcc-tools && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./scripts/ .
