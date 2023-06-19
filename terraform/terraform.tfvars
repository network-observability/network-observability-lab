pvt_key = "~/.ssh/id_rsa_do"  # private key location, so Terraform can use it to log in to new Droplets
digitalocean_ssh_key_name = "network-observability-lab"  # replace with your SSH key identifier in DO
vm_region = "nyc3"  # replace with your preferred region, for example fra1
vm_size = "s-2vcpu-4gb"  # replace with your preferred Droplet size, for example s-4vcpu-8gb
reader = "reader"  # replace with your preferred username
