resource "digitalocean_droplet" "netobs_vm" {
  image  = "ubuntu-20-04-x64"
  name   = format("%s-%s", "netobs", var.reader)
  region = var.vm_region
  size   = var.vm_size
  ssh_keys = [
    data.digitalocean_ssh_key.terraform.id
  ]
  tags = [
    "netobs-vm"
  ]

  connection {
    host        = self.ipv4_address
    user        = "root"
    type        = "ssh"
    private_key = file(var.pvt_key)
    timeout     = "2m"
  }

  provisioner "file" {
    source      = var.pub_ssh_key
    destination = "/tmp/temp.pub"
  }

  provisioner "remote-exec" {
    inline = [
        # Set up SSH keys
        "cat /tmp/temp.pub >> ~/.ssh/authorized_keys",
        "sudo apt-get update -y",
        # Install Docker
        "curl -fsSL https://get.docker.com -o get-docker.sh",
        "sudo sh get-docker.sh",
        # Install containerlab
        "bash -c \"$(curl -sL https://get.containerlab.dev)\"",
        # Install Python 3.9
        "sudo add-apt-repository -y ppa:deadsnakes/ppa",
        "sudo apt update -y",
        "sudo apt install -y python3.9",
        "sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1",
        "sudo apt-get install -y python3-pip",
        # Install netobs
        "git clone https://github.com/network-observability/network-observability-lab.git",
        "cd network-observability-lab && git checkout main && cp example.env .env && pip install .",
    ]
  }
}

resource "digitalocean_firewall" "netobs" {
  name = "netobs-${var.reader}"

  droplet_ids = [digitalocean_droplet.netobs_vm.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8080"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "9000-9999"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "3000-3100"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "4200"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "icmp"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "tcp"
    port_range            = "53"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "53"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

output "vm_ips" {
  value = "netobs-vm: ${digitalocean_droplet.netobs_vm.ipv4_address}"
}

output "ssh_command" {
  value = "ssh -i ${var.pvt_key} root@${digitalocean_droplet.netobs_vm.ipv4_address}"
}
