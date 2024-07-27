# Remote Machine Setup

This directory contains instructions for deploying a remote droplet (virtual machine) on DigitalOcean to follow along with the labs stored in this repository.

The virtual machine is configured to run the network observability lab using the `netobs` utility tool. If you are following along with the book, you can use this virtual machine to run the labs presented in the book.

## Requirements

To run the commands used to deploy and provision a DigitalOcean droplet, you need to have the following:

- **The `netobs` tool installed on your system**: Later in this section, we explain how to install it.
- **A DigitalOcean account**: IMPORTANT: Deploying a droplet/virtual machine costs money, so we spent a good amount of time automating the setup and removal of the droplet to optimize costs.
  - **SSH keys to access the virtual machine**: You will need to upload your public key to DigitalOcean and retrieve its SSH fingerprint. For information on how to create SSH keys, check out the [official documentation](https://docs.digitalocean.com/products/droplets/how-to/add-ssh-keys/). This step ensures secure and passwordless access to your droplet.
  - **A DigitalOcean API key**: This key is necessary to programmatically interact with the DigitalOcean API for tasks like creating and managing droplets. For information on how to create an API key, check out the [official documentation](https://docs.digitalocean.com/reference/api/create-personal-access-token/).
- **Forked networked-observability-lab repo**: By forking this repository, you are able to make the changes you desire and follow along with the example and tasks presented in the book. For more information on how to fork a GitHub repository see the [official documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo).

Make sure you have these prerequisites ready before proceeding with the setup.

## Quickstart

For a straightforward deployment of the virtual machine, you can run the following commands from your forked repository:

```shell
# On your local machine clone your forked repository and go to its root location
git clone https://github.com/<your-user>/network-observability-lab.git
cd network-observability-lab

# Setup environment variables (edit the .env file to your liking)
cp example.env .env
cp example.setup.env .setup.env

# Edit the .setup.env file to replace the DigitalOcean API key among the others listed there.
vim .setup.env

# Install netobs
pip install .

# Spin up the DigitalOcean droplet build process
netobs setup deploy
```

Running netobs will initiate Ansible playbooks to set up and configure the DigitalOcean droplet. It will prompt you for details about the droplet's specifications and location, providing default values:

- **Droplet image**: The OS image for the droplet. We recommend using ubuntu. Most labs in this book are tested on Debian distributions.
- **Droplet size**: Specifies the resources for the droplet. We suggest using s-4cpu for a balance of performance and cost. For faster builds, you may opt for higher specs.
- **Droplet region**: Choose a DigitalOcean site near you. Refer to this list for available regions.
The Ansible playbook will use the .setup.env environment variables and specified droplet details to build, provision, and configure the droplet with netobs and containerlab, running the batteries-included lab.

To explore or perform the labs presented in the book, connect to the droplet using SSH. You can get the details on how to connect by running the command `netobs setup list`:

```bash
❯ netobs setup show

TASK [Show SSH command] ****************************************************************
ok: [netobs-droplet] => {}

MSG:

ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa root@<droplet-ip>
```

## Remove Droplet

To completely destroy the droplet, use the following command:

```bash
netobs setup destroy
```

This action is irreversible, so ensure you commit any changes to your forked repository before proceeding.

## Troubleshooting

If you encounter issues with the Ansible deployment, use the --verbose flag for detailed output:

```bash
netobs setup deploy --verbose
```
