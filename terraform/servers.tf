resource "digitalocean_droplet" "netobs_vm" {
  image  = "ubuntu-22-04-x64"
  name   = format("%s-%s", "netobs", var.user)
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

  provisioner "file" {
    source      = "../.env"
    destination = "/tmp/.env"
  }

  provisioner "file" {
    content = <<EOF

127.0.0.1 prometheus
127.0.0.1 grafana
127.0.0.1 loki
127.0.0.1 nautobot

    EOF
    destination = "/tmp/network-observability-lab.txt"
  }

  provisioner "remote-exec" {
    inline = [
        # Set up SSH keys
        "cat /tmp/temp.pub >> ~/.ssh/authorized_keys",
        "sudo apt-get update -y",
        "sleep 30"
    ]
  }

  provisioner "remote-exec" {
    inline = [
        # Install Docker
        "curl -fsSL https://get.docker.com -o get-docker.sh",
        "sudo sh get-docker.sh",
        "sleep 60",
    ]
  }

  provisioner "remote-exec" {
    inline = [
        # Install Python with miniconda
        "curl https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o ~/miniconda.sh",
        "bash ~/miniconda.sh -b -p $HOME/miniconda",
        "export PATH=\"$HOME/miniconda/bin:$PATH\"",
        "echo 'export PATH=\"$HOME/miniconda/bin:$PATH\"' >> ~/.bashrc",
        "sleep 30",
    ]
  }

  provisioner "remote-exec" {
    inline = [
        # Update /etc/hosts
        "cat /tmp/network-observability-lab.txt >> /etc/hosts",
        # Install containerlab
        "bash -c \"$(curl -sL https://get.containerlab.dev)\"",
        "sleep 60",
    ]
  }

  provisioner "remote-exec" {
    inline = [
        # Install netobs
        "git clone https://github.com/network-observability/network-observability-lab.git",
        "cd network-observability-lab && git checkout main && mv /tmp/.env .env && pip install .",
        "sleep 60",
    ]
  }

  ############################# ONLY NEEDED IF PASSING IN A CEOS IMAGE #############################
  provisioner "file" {
    source      = var.lab_image.local_path
    # source      = "~/tmp/images/arista/cEOS-lab-4.29.2F.tar"
    # destination = "/tmp/${var.lab_tarimage}"
    destination = "/tmp/${var.lab_image.tar_name}"
  }

  provisioner "remote-exec" {
    inline = [
        # Import cEOS image
        # "docker import /tmp/${var.lab_tarimage} ${var.lab_image_name}",
        "docker import /tmp/${var.lab_image.tar_name} ${var.lab_image.image_name}",
    ]
  }
  ##################################################################################################

  # Prepare the lab
  provisioner "remote-exec" {
    inline = [
        "export PATH=\"$HOME/miniconda/bin:$PATH\"",
        "cd network-observability-lab && git checkout ${var.github_branch}",
        "netobs lab prepare --scenario batteries-included"
    ]
  }
}

resource "digitalocean_firewall" "netobs" {
  name = "netobs-${var.user}"

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

output "vm_endpoints" {
  value = {
    nautobot = "http://${digitalocean_droplet.netobs_vm.ipv4_address}:8080",
    grafana = "http://${digitalocean_droplet.netobs_vm.ipv4_address}:3000",
    prometheus = "http://${digitalocean_droplet.netobs_vm.ipv4_address}:9090",
  }
}

output "ssh_command" {
  value = "ssh -o StrictHostKeyChecking=no -i ${var.pvt_key} root@${digitalocean_droplet.netobs_vm.ipv4_address}"
}
