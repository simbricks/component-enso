#!/bin/bash -eux
#
# Installs Ensō into a guest image. Driven by EnsoDiskImage via enso.pkr.hcl,
# which boots the image the simulated hosts will run and executes this inside
# it. Do not run it on your workstation: it apt-installs packages, writes to
# /lib/modules and installs into /usr/local.
#
# Because packer boots the very image the driver will be loaded into, `uname -r`
# here is already the right kernel, so Ensō's own setup.sh does the whole job:
# dependencies, hugepages, the kernel module, and the meson build of the
# userspace with the buffer sizes the behavioral model expects.
#
# The one thing added afterwards is putting the module where modprobe can find
# it; setup.sh leaves it in Ensō's build tree, which would force every
# simulation run to rebuild it. EnsoLinuxHost only modprobes.
set -eux
export DEBIAN_FRONTEND=noninteractive

ENSO_REPO="${ENSO_REPO:-https://github.com/crossroadsfpga/enso}"
ENSO_BRANCH="${ENSO_BRANCH:-simbricks-24.04}"

# Must match EnsoLinuxHost.enso_parent_dir / .enso_name.
ENSO_DIR="${ENSO_DIR:-/root/enso}"

KVER=$(uname -r)

# The kernel headers come with the image's kernel, whether that is a distro one
# or a custom SimBricks build installed from a .deb. Do not apt-install them:
# there is no linux-headers package to fetch for a custom kernel.
if [ ! -d "/lib/modules/$KVER/build" ]; then
    echo "no kernel build tree at /lib/modules/$KVER/build -- the image needs" >&2
    echo "the headers matching its kernel to build the Ensō driver." >&2
    exit 1
fi

# Only what Ensō's setup.sh does not install itself. sudo, because its scripts
# and scripts/ensogen.sh use it and the base image may not have it.
apt-get -y update
apt-get -y install build-essential git ca-certificates sudo \
    libnuma-dev rsync bc libelf-dev kmod pkg-config

git clone "$ENSO_REPO" "$ENSO_DIR"
cd "$ENSO_DIR"
git checkout "$ENSO_BRANCH"

# Installs dependencies, reserves hugepages, builds and loads the kernel module,
# then meson-builds and installs the userspace. --no-quartus skips the FPGA
# toolchain check; it still fetches the bitstream, which we never program.
./setup.sh --no-quartus

# setup.sh leaves the module in the build tree, so make it modprobe-able.
install -Dm644 "$ENSO_DIR/software/kernel/linux/intel_fpga_pcie_drv.ko" \
    "/lib/modules/$KVER/extra/intel_fpga_pcie_drv.ko"
depmod -a "$KVER"

# ensogen.sh resolves its binaries through $ENSO_DIR/build, so leave the tree in
# place. Check that what the application classes invoke actually exists.
test -x "$ENSO_DIR/build/software/examples/echo"
test -x "$ENSO_DIR/build/software/examples/ensogen"
test -x "$ENSO_DIR/build/scripts/get_pcap_pkt_size"
