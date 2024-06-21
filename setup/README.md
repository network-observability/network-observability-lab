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

```bash
# On your local machine
git clone https://github.com/<your-user>/network-observability-lab.git
# Setup environment variables (edit the .env file to your liking)
cp example.env .env
cp example.setup.env .setup.env

# Edit the .env file to replace the Digital Ocean API key (using vim for example).
# For example: TF_VAR_digitalocean_token=<DIGITAL_OCEAN_API_KEY>
vim .env

# Install the python dependencies
pip install .

# Start the terraform deployment (this will take a few minutes)
netobs vm deploy
```

`netobs` will kick off a Terraform deployment process to stand up and configure the Digital Ocean VM. Here is an example output of the `netobs vm deploy` command:

```bash
$ netobs vm deploy
# .... output omitted for brevity
[06:33:29] Successfully ran: terraform apply
──────────────────────────────────────────────── End of task: terraform apply ────────────────────────────────────────────────

           Lab VM deployed
           Running command: terraform -chdir=./terraform/ output -json
           Successfully ran: terraform output
─────────────────────────────────────────────── End of task: terraform output ────────────────────────────────────────────────

           VM IP: netobs-vm: <digital-ocean-vm-ip>
           VM SSH command: ssh -i ~/.ssh/id_rsa_do root@<digital-ocean-vm-ip>
```

At this point, it will print out the IP address of the VM and the SSH command to connect to it. You can now connect to the VM and start the network-observability lab.

Alternatively, if you don't want to install the `netobs` utility, you can run the following commands to start the terraform deployment:

```bash
# Export the Digital Ocean API key
export TF_VAR_digitalocean_token=<DIGITAL_OCEAN_API_KEY>

# Change directory to the terraform deployment
cd terraform

# Start the terraform deployment
terraform init

# Validate the terraform deployment
terraform validate

# Check the the terraform deployment plan (optional)
terraform plan

# Start the terraform deployment
terraform apply
```

## Destroy VM

To destroy the VM, you can run the following commands:

```bash
netobs vm destroy
```

This will destroy the VM. Here is an example output of the `netobs vm destroy` command:

```bash
$ netobs vm destroy
# .... output omitted for brevity
digitalocean_firewall.netobs: Destroying... [id=714669cf-1ac1-46ae-84b3-aaabbbccc]
digitalocean_firewall.netobs: Destruction complete after 1s
digitalocean_droplet.netobs_vm: Destroying... [id=361165777]
digitalocean_droplet.netobs_vm: Still destroying... [id=361165777, 10s elapsed]
digitalocean_droplet.netobs_vm: Still destroying... [id=361165777, 20s elapsed]
digitalocean_droplet.netobs_vm: Destruction complete after 21s

Destroy complete! Resources: 2 destroyed.
[06:52:36] Successfully ran: terraform destroy
─────────────────────────────────────────────── End of task: terraform destroy ───────────────────────────────────────────────

           Lab VM destroyed
```

Alternatively, you can run the following commands:

```bash
# Export the Digital Ocean API key
export TF_VAR_digitalocean_token=<DIGITAL_OCEAN_API_KEY>

# Change directory to the terraform deployment
cd terraform

# Destroy the terraform deployment
terraform destroy
```

## Customizing the VM

If you want to customize the VM, you can edit the `terraform/terraform.tfvars` file to your liking. For example, you can change the VM size, region, and other settings. For example:

```ini
# terraform/terraform.tfvars

# Change Digital Ocean region to FRA1
region = "fra1"

# Select a larger VM size
size = "s-4vcpu-8gb"
```

You can also modify parameters like the SSH key path and the SSH key name used in your Digital Ocean account. The default values are set to follow the examples in the book.

After you have made the changes, you can run the following commands to apply the changes:

```bash
netobs vm deploy
```

Alternatively, you can run the following commands:

```bash
# Export the Digital Ocean API key
export TF_VAR_digitalocean_token=<DIGITAL_OCEAN_API_KEY>

# Change directory to the terraform deployment
cd terraform

# Start the terraform deployment
terraform apply
```

## Troubleshooting

If you run into any issues with the terraform deployment, you can run the following commands to get more information:

```bash
# Export the Digital Ocean API key
export TF_VAR_digitalocean_token=<DIGITAL_OCEAN_API_KEY>

# Change directory to the terraform deployment
cd terraform

# Check the terraform deployment plan
terraform plan

# Check the terraform deployment state
terraform state list

# Check the terraform deployment state for a specific resource
terraform state show <resource-name>
```