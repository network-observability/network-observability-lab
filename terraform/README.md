# Terraform deployment for `netobs-vm`

This directory contains the terraform deployment for the `netobs-vm` virtual machine. The virtual machine is hosted in Digital Ocean and is used to run the network-observability lab with `netobs` utility tool.

## Requirements

To run the terraform deployment you must have:

- `terraform` installed in your system
- `doctl` installed in your system
- A Digital Ocean account with an API key

## Quickstart

To get started with the terraform deployment, you can run the following commands:

```bash
# Setup environment variables (edit the .env file to your liking)
cp example.env .env

# Install the python dependencies
pip install .

# Start the terraform deployment
netobs vm deploy
```

`netobs` is a utility tool that provides functions to interact and manage the network lab and observability stack in the repository. It is designed to simplify the process of managing and monitoring network infrastructure by providing a set of helpful commands and utilities.

Alternatively, you can run the following commands to start the terraform deployment:

```bash
# Start the terraform deployment
terraform init

# Start the terraform deployment
terraform apply
```
