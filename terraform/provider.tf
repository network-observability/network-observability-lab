terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

variable "digitalocean_token" {
  type = string
  description = "Digital Ocean API token"
}
variable "pvt_key" {
  type = string
  description = "path to rsa private key"
}
variable vm_region {
  type = string
  description = "region where VM will be created"
  default = "nyc3"
}
variable "vm_size" {
  type = string
  description = "size of VM"
  default = "s-2vcpu-4gb"
}
variable "reader" {
  type = string
  description = "reader name"
}
variable "pub_ssh_key" {
  type = string
  description = "path to rsa public key, that will be copied to VMs"
  default = "~/.ssh/id_rsa_do.pub"
}
variable "digitalocean_ssh_key_name" {
  type = string
  description = "name of ssh key registered in Digital Ocean"
}


provider "digitalocean" {
  token = var.digitalocean_token
}

data "digitalocean_ssh_key" "terraform" {
  name = var.digitalocean_ssh_key_name
}
