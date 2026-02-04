# Webinar

This code supports a 4-hour webinar format.

## Content

## How to bootstrap

### Linux

1. Fork (in GitHub) and Clone the Git Repository
```
$ git clone https://github.com/<your-user>/network-observability-lab.git
$ cd network-observability-lab
```
2. Install the netobs tool  (use a virtualenv!)
```
(.venv)$ pip install .
```
3. Setup environment files
```
$ cp example.env .env
```
4. Deploy the stack with Docker (dependency)
```
(.venv)$ netobs lab deploy \
    --scenario webinar \
    --topology ./chapters/webinar/containerlab/lab.yml
```

### Digital Ocean Linux VM

1.Create a Digital Ocean account: https://www.digitalocean.com/try/free-trial-offer
2. Fork (in GitHub) and Clone the Git Repository
```
$ git clone https://github.com/<your-user>/network-observability-lab.git
$ cd network-observability-lab
```
3. Install the netobs tool  (use a virtualenv!)
```
(.venv)$ pip install .
```
4. Create a Digital Ocean API token
5. Create an SSH key pair and retrieve its fingerprint
```
$ ssh-keygen -t rsa -b 4096 -C "network-observability-lab" -f ~/.ssh/id_rsa_do
```
6. Setup environment files
```
$ cp example.setup.env .setup.env
$ cp example.env .env
SSH_KEY_PATH="~/.ssh/id_rsa_do"
NETOBS_REPO="https://github.com/<your-username>/network-observability-lab.git"
```
7. Create a Digital Ocean droplet (it takes some minutes)
```
(.venv)$ netobs setup deploy --scenario webinar \
  --topology ./chapters/webinar/containerlab/lab.yml \
  --vars-topology ./chapters/webinar/containerlab/lab_vars.yml
[17:15:12] Running command: ansible-playbook setup/create_droplet.yml -i setup/inventory/localhost.yaml
Enter the droplet image [ubuntu-22-04-x64]:
Enter the droplet size [s-8vcpu-16gb]: s-4vcpu-8gb
Enter the droplet region [fra1]:
PLAY [Stand up netobs-droplet] ****************************************************************************
```

