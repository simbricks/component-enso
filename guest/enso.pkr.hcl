# Packer template that installs Ensō into an existing SimBricks guest image.
#
# It is a specialization step, not an image build: it boots the image the
# simulated hosts would otherwise boot, runs install-enso.sh inside it, and
# writes the result to <output>/<name>. The kernel is untouched, so the source
# image's boot artifacts still apply and nothing needs extracting.
#
# EnsoDiskImage drives this; see enso_sys_py/.../system/enso.py. To run it by
# hand:
#
#   packer init enso.pkr.hcl
#   packer build -var source_image=/path/to/base \
#       -var 'scripts=["/path/to/component-enso/guest/install-enso.sh"]' \
#       -var output=/tmp/enso-image/enso enso.pkr.hcl

packer {
  required_plugins {
    qemu = {
      source  = "github.com/hashicorp/qemu"
      version = "~> 1.1"
    }
  }
}

variable "source_image" {
  type        = string
  description = "Local path of the image to install Ensō into."
}

variable "source_checksum" {
  type        = string
  default     = "none"
  description = "Checksum for source_image; 'none' for a local file."
}

variable "name" {
  type        = string
  default     = "enso"
  description = "Image name; also the disk filename."
}

variable "output" {
  type        = string
  default     = "output-enso"
  description = "Output directory."
}

variable "scripts" {
  type        = list(string)
  default     = []
  description = "Guest provisioning scripts, run in order. Normally just install-enso.sh."
}

variable "memory" {
  type    = number
  default = 16384
}

variable "cpus" {
  type    = number
  default = 4
}

variable "disk_size" {
  type    = string
  default = "16G"
}

variable "qemu_binary" {
  type    = string
  default = "qemu-system-x86_64"
}

variable "accelerator" {
  type    = string
  default = "tcg" # "tcg" without nested virt
}

variable "ssh_username" {
  type    = string
  default = "ubuntu"
}

variable "ssh_password" {
  type    = string
  default = "ubuntu"
}

variable "compressed" {
  type    = bool
  default = true
}

# Forwarded into the guest provisioners; default off the host env, empty = none.
variable "http_proxy" {
  type    = string
  default = env("http_proxy")
}

variable "https_proxy" {
  type    = string
  default = env("https_proxy")
}

locals {
  # Run each provisioner script as root, forwarding any proxy.
  execute_command = "chmod +x {{.Path}}; sudo -E env {{.Vars}} http_proxy=${var.http_proxy} https_proxy=${var.https_proxy} {{.Path}}"
}

source "qemu" "enso" {
  iso_url          = var.source_image
  iso_checksum     = var.source_checksum
  disk_image       = true
  disk_size        = var.disk_size
  format           = "qcow2"
  accelerator      = var.accelerator
  qemu_binary      = var.qemu_binary
  memory           = var.memory
  cpus             = var.cpus
  headless         = true
  net_device       = "virtio-net"
  disk_interface   = "virtio"
  disk_compression = var.compressed

  # cloud-init NoCloud seed over packer's HTTP server (via SMBIOS serial), so no
  # CD image and no xorriso/mkisofs on the host. Harmless when the source image
  # already has the user: cloud-init just reapplies it.
  http_directory   = "${path.root}/http"
  qemuargs         = [
    ["-smbios", "type=1,serial=ds=nocloud;instance-id=enso;seedfrom=http://{{ .HTTPIP }}:{{ .HTTPPort }}/"],
    ["-serial", "file:/tmp/qemu-serial-enso.log"], # diagnostic: guest console -> file
  ]

  ssh_username     = var.ssh_username
  ssh_password     = var.ssh_password
  ssh_timeout      = "10m"

  shutdown_command = "sudo shutdown -P now"
  output_directory = var.output
  vm_name          = var.name
}

build {
  sources = ["source.qemu.enso"]

  provisioner "shell" {
    scripts         = var.scripts
    execute_command = local.execute_command
  }
}
