# component-enso

SimBricks component repo for [Ensō](https://github.com/crossroadsfpga/enso), the streaming NIC interface
from CMU. It bundles the Ensō behavioral model, the Python packages that integrate it into the SimBricks
orchestration framework, and the guest-side provisioning that puts Ensō's driver and userspace into the
disk image — all shipped as conda packages so users install only the piece they need.

For Ensō itself — what it is, its API, its own build — see [its documentation](https://enso.cs.cmu.edu) and
[repository](https://github.com/crossroadsfpga/enso). This README only covers what is specific to the
SimBricks integration. Two properties of Ensō shape that integration: it is driven from userspace and has
**no kernel network device**, and, like Corundum, it has a **guest-side** piece that must be in the image
the simulated hosts boot. See [Guest software and disk images](#guest-software-and-disk-images).

## Credits

The Ensō behavioral model in [`enso_bm/`](enso_bm/) was written by **[Hugo Sadok](https://github.com/hsadok)**,
who also created Ensō itself. He contributed it to SimBricks as
[simbricks#138](https://github.com/simbricks/simbricks/pull/138) and later updated it in his
[fork](https://github.com/hsadok/simbricks/tree/enso_bm). That work predates SimBricks' move to out-of-tree
components, so this repository re-packages it for the current architecture; the C++ model is his, carried
over essentially unchanged.

Ensō is described in ["Ensō: A Streaming Interface for NIC-Application
Communication"](https://www.usenix.org/conference/osdi23/presentation/sadok) (OSDI '23) by Hugo Sadok,
Nirav Atre, Zhipeng Zhao, Daniel S. Berger, James C. Hoe, Aurojit Panda, Justine Sherry and Ren Wang.

See [`enso_bm/VENDOR.md`](enso_bm/VENDOR.md) for the exact upstream commit, what was taken, and the local
modifications.

## Layout

| Path | Description |
|---|---|
| `enso_bm/` | The Ensō behavioral model — vendored C++ sources plus our build. Produces `simb_enso_bm`. |
| `enso_bm/VENDOR.md` | Upstream commit, license and the local modifications applied to the vendored sources. |
| `enso_sys_py/` | Python *system* package (`simbricks-enso-sys-py`), exposing `simbricks.components.enso.system`. |
| `enso_sim_bm_py/` | Python *simulation* package (`simbricks-enso-sim-bm-py`), exposing `simbricks.components.enso.simulation.behavioral`. |
| `conda-recipes/simbricks-enso-sys-py/` | Conda recipe for the noarch system python package. |
| `conda-recipes/simbricks-enso-sim-bm-py/` | Conda recipe for the noarch simulation python package. |
| `conda-recipes/simbricks-enso-sim-bm-bin/` | Conda recipe for the compiled model (`simbricks-enso-sim-bm-bin`). |
| `conda-recipes/conda_build_config.yaml` | Shared version / URL variables used by all recipes. |
| `enso_sys_py/…/system/image.py` | `enso_image()` — the guest image, as a layer on the SimBricks `base` image. |
| `enso_sys_py/…/system/data/install-enso.sh` | The guest-side install step that layer runs. Shipped inside the package, so building an image needs no checkout. |
| `examples/enso_echo.py` | Runnable virtual prototype: EnsoGen against an Ensō echo server. |
| `Makefile` | Top-level driver for the builds below. |
| `.devcontainer/conda-build/` | VS Code dev container providing a ready-to-use conda build environment. |

## Conda packages

This repo produces three packages:

- **`simbricks-enso-sys-py`** — noarch Python package with the *system* components: `EnsoNIC`,
  `EnsoLinuxHost`, the `EnsoEchoServer` / `EnsoGen` applications, and `enso_image()`. These describe *what*
  is being built and carry no simulator dependency, so a system description can be written (and shared)
  without installing the model. It also carries the guest install script, and depends on
  `simbricks-imagebuild-packer` (which pulls in `packer`) for the image build.
- **`simbricks-enso-sim-bm-py`** — noarch Python package with `EnsoNicSim`, the simulator choice for an
  `EnsoNIC`. It builds on the system package (both live in the shared `simbricks.components.enso` namespace)
  and pins it with `==` to the co-built version.
- **`simbricks-enso-sim-bm-bin`** — the compiled behavioral model, installed as **`simb_enso_bm` in
  `$PREFIX/bin`**. That name is not incidental: `EnsoNicSim` passes `executable="simb_enso_bm"` and the
  binary is resolved through `PATH`. The package depends on `simbricks-enso-sim-bm-py` at the same version,
  so installing the simulator also pulls in its orchestration glue (and the system package).

The `bm` in the names is the *flavor* — a behavioral model. Ensō also has real FPGA RTL upstream, so an
`rtl` flavor can be added alongside this one later without moving anything.

External dependencies that are *not* built here — `simbricks-lib` (needed to build the model) and
`simbricks-orchestration` / `simbricks-utils` / `simbricks-imagebuild-packer` (runtime deps of the python
packages) — are resolved automatically from the public SimBricks conda channel
(`https://conda.simbricks.io/latest`, wired into the build via the Makefile's `SIMB_CONDA_CHANNEL`). You do
**not** need to install them by hand. The channel has to be `latest`: `simbricks-imagebuild-packer` is not
on `stable` yet.

## Prerequisites

- A conda installation with `conda build` available. The easiest path is the bundled dev container
  (`.devcontainer/conda-build/`), based on the SimBricks `conda-build-env` image — "Reopen in Container" in
  VS Code and everything (conda-build, toolchain, channels) is ready.
- If not using the dev container: a C++17 toolchain, `make`, and Boost (`libboost-devel`) — the model links
  `-lboost_fiber -lboost_context` because SimBricks' `nicbm::MultiNicRunner` runs each NIC on a fiber.

## Building the conda packages

```sh
# Build all three packages in dependency order: the python packages first, then
# the binary package (which depends on them and resolves them from the local
# channel). External deps are pulled from the SimBricks channel automatically.
make conda-packages          # this is also the default `make` target

# Or build them individually.
make enso-sys-py-conda
make enso-sim-bm-py-conda    # builds enso-sys-py-conda first
make enso-sim-bm-bin-conda

# Redirect conda-build output if desired.
make conda-packages OUTPUT_FOLDER=./conda-out
```

Build these sequentially (do not pass `-j`), so each build finds the packages produced by the previous one
in the local channel.

## Guest software and disk images

The image the simulated hosts boot has to carry the Ensō guest software — its `intel_fpga_pcie_drv` kernel
module and its userspace library and example binaries. Hugepages are set up at boot instead, see
[At run time](#at-run-time-driver-and-hugepages).

Getting the software into an image is one guest-side script,
[`install-enso.sh`](enso_sys_py/simbricks/components/enso/system/data/install-enso.sh): it clones Ensō,
hands off to Ensō's own `setup.sh`, and then installs the built module under `/lib/modules/<kver>/extra` and
runs `depmod`, so a plain `modprobe` finds it. Two constraints follow from the kernel module: the image
needs a kernel build tree at `/lib/modules/$(uname -r)/build`, and the script must run **on the kernel the
simulated hosts will boot** — an out-of-tree module is tied to the exact kernel it was compiled against.

### Building the image

`enso_image()` describes that as a layer on top of the SimBricks `base` image, in SimBricks' layered
image-build API:

```python
from simbricks.components.enso.system import enso_image

enso_img = enso_image(syst)
host.add_disk(enso_img)
```

That is the whole wiring, and it is what [`examples/enso_echo.py`](examples/enso_echo.py) does. The build
runs on the runner while the simulation is prepared. It returns a
[`PackerImage`](https://github.com/simbricks/simbricks/tree/main/symphony/imagebuild-packer), so packer
boots the `base` image and runs the install inside it — which is exactly what the kernel-module constraint
above demands. The cheaper offline backend (`GuestfsImage`, libguestfs) is *not* usable here: in its
appliance `uname -r` names the appliance's kernel, and Ensō's `setup.sh` insmods the module it just built.

Because it is an ordinary `PackerImage`, the build can still be adjusted — `enso_img.cleanup = False`,
`enso_img.accelerator = "tcg"`, `enso_img.mem_size`, `.cpus`, `.disk_size`. The defaults are 16 GiB of disk,
16 GiB of RAM and 4 vCPUs for the build machine, carried over from the packer template this replaces.

The kernel the host simulator boots now comes out of the built image itself — packer collects `vmlinuz` (and
`initrd`, `vmlinux`) during the build and they are cached with it. Nothing reads `images/base/boot/` any
more.

### Caching

Without a cache the image is rebuilt on every run, which is slow. Give the runner one:

```sh
simbricks-run --image-cache-dir /var/cache/simbricks-images \
              --image-cache-size 100G \
              --global-input-dir <dir> examples/enso_echo.py
```

Entries are keyed by a content hash of the base image plus every layer, stored as compressed qcow2 deltas,
and evicted under the size limit. The second run of the same prototype skips the build entirely.

Changing the install script, or the `enso_repo` / `enso_branch` / `enso_dir` arguments, changes the hash and
rebuilds. **New commits on the same branch do not** — the hash covers the branch name, not what it points
at. Pin a commit or drop the cache entry when that matters.

### What the runner needs

`packer`, `qemu-system-x86_64`, `qemu-img` and `xorriso` (packer builds the cloud-init seed as a CD), plus
the base image. `/dev/kvm` is optional but worth having: without it packer falls back to `tcg` and the build
VM takes considerably longer, which is why the SSH timeout adapts (20 minutes with KVM, 90 without).

Two things are required of the **base image**, and a build that hangs at `Waiting for SSH to become
available` is almost certainly one of them:

- **Its kernel must be able to mount iso9660** (`CONFIG_ISO9660_FS`). Packer hands cloud-init its seed as
  a CD, under a fresh instance-id, and cloud-init then *has* to read it: on a new-instance boot with no
  user-data it locks the `ubuntu` account (`passwd -l`), regenerates the host keys and reconfigures the
  network from a fallback heuristic — so a kernel without iso9660 does not "work by accident", it fails
  every time. Stock distro kernels have it; image-builder's custom kernel needs
  `CONFIG_ISO9660_FS=y` in `kernel/config-5.15.93`.
- Build it with [image-builder](https://github.com/simbricks/image-builder) of **2026-08-12 or later**,
  which puts `dummy.numdummies=0 bonding.max_bonds=0` on the kernel command line. An older base carries a
  `dummy0` that cloud-init's fallback NIC pick prefers over the real interface, which turns any boot where
  the seed is not read into a two-minute stall with no network.

When a build does hang, the guest's own console is at `tmp/imgs/build.*/serial.log`, and its
`/var/log/cloud-init.log` can be read straight out of the image with
`virt-cat -a <image> /var/log/cloud-init.log`.

Nothing has to be shipped alongside the run. The install script travels inside the serialized system, so a
remote runner needs no input artifacts for it.

### Using a prebuilt image instead

If you would rather build the image out of band, install it where orchestration looks for images —
`images/<name>/` under the directory passed to `simbricks-run --global-input-dir` — and use it directly, with
no image build in the loop:

```python
enso_img = system.DistroDiskImage(syst, "enso")
host.add_disk(enso_img)
```

The image then has to carry its own boot artifacts in `images/<name>/boot/`.

### At run time: driver and hugepages

Independent of how the image was built, `EnsoLinuxHost` emits, after checkpoint restore: the hugetlbfs
mount and `nr_hugepages` reservation, `modprobe uio` + `modprobe intel_fpga_pcie_drv`, and the `mknod` +
`chmod` of `/dev/intel_fpga_pcie_drv` that Ensō's own `load` script would do (a bare `modprobe` leaves no
device node when udev is not configured for it).

The module is never compiled in the guest: that happens once, in the image, where it costs no simulated
time.

It also deliberately **skips** the netdev configuration a normal `LinuxHost` emits. `LinuxHost.prepare_post_cp`
brings up an `ethN` and assigns an IP for every attached NIC, asserting that one was set — but an Ensō NIC
has no netdev, so `EnsoLinuxHost` calls the grandparent implementation and re-emits only the driver loading.
Consequently **do not call `add_ipv4()`** on an `EnsoNIC`; it would have no effect.

`EnsoLinuxHost.enso_parent_dir` / `.enso_name` (`/root/enso`) must agree with the script's `ENSO_DIR`: that
is where the application classes `cd` into and where `ensogen.sh` resolves its binaries.

### Sizes must agree on both sides

The behavioral model is compiled with fixed `ENSO_PIPE_SIZE` / `NOTIFICATION_BUF_SIZE` values, and the
guest software must be built with the matching meson options. The defaults line up, so out of the box
there is nothing to do — but keep it in mind when changing either side, and see
[`enso_bm/VENDOR.md`](enso_bm/VENDOR.md).

## Local development

The Makefile targets are deliberately split so that, while working on this repo, you can build and test the
model or the Python packages **directly** — without going through the conda packaging defined here. Install
any *other* SimBricks dependencies from the conda channel and iterate on just the piece you are changing.

### Behavioral model

```sh
# Build enso_bm/simb_enso_bm. Point the SimBricks include/lib dirs at your env
# (e.g. your conda prefix) so it can link.
make enso-build \
    SIMBRICKS_INC_DIR="$CONDA_PREFIX/include" \
    SIMBRICKS_LIB_DIR="$CONDA_PREFIX/lib"

# Install it as $(PREFIX)/bin/simb_enso_bm (builds first if needed).
make enso-install PREFIX="$PWD/out"

# Reset the build.
make clean
```

### Python packages

```sh
# Editable installs — iterate on the python code without reinstalling.
# The system package is installed first so the simulation package's imports resolve.
make enso-python-develop
```

### Iterating on Ensō itself

The install script clones `ENSO_REPO` at `ENSO_BRANCH` (`crossroadsfpga/enso`, branch `simbricks-24.04`)
into `ENSO_DIR`. Point the image at your own work through the constructor, which exports all three into the
script when the layer runs:

```python
enso_img = enso_image(syst, enso_repo="https://github.com/me/enso", enso_branch="my-work")
```

They are part of the image's content hash, so changing one rebuilds rather than reusing a cached image.
(Exporting them next to `simbricks-run` still has no effect — nothing carries the orchestration host's
environment into the guest.)

`make guest-install` runs the script directly, for when you are already inside a guest, and there the
environment does apply:

```sh
ENSO_REPO=https://github.com/me/enso ENSO_BRANCH=my-work make guest-install
```

An edit to the script changes the hash too, so it lands in the next run.

## Make target reference

| Target | Description |
|---|---|
| `all` (default) | Build all conda packages (alias for `conda-packages`). |
| `conda-packages` | Build all three conda packages in dependency order. |
| `enso-sys-py-conda` | Build the `simbricks-enso-sys-py` conda package. |
| `enso-sim-bm-py-conda` | Build the `simbricks-enso-sim-bm-py` conda package (builds `enso-sys-py-conda` first). |
| `enso-sim-bm-bin-conda` | Build the `simbricks-enso-sim-bm-bin` conda package. |
| `enso-build` | Build the behavioral model binary. |
| `enso-install` | Install the model into `$(PREFIX)/bin/simb_enso_bm`. |
| `guest-install` | Run the packaged `install-enso.sh` directly. For use inside a guest. |
| `enso-python-develop` | Editable (`pip install -e`) installs of both python packages. |
| `pypi-build` / `pypi-publish` | Build / publish the python wheels with poetry. |
| `clean` | Remove the model's build artifacts, `out/` and the python `dist/` dirs. |

### Useful variables

| Variable | Default | Purpose |
|---|---|---|
| `PREFIX` | `$(CURDIR)/out` | Install prefix for `enso-install`. |
| `SIMBRICKS_INC_DIR` | `$(PREFIX)/include` | SimBricks headers for the model build. |
| `SIMBRICKS_LIB_DIR` | `$(PREFIX)/lib` | SimBricks static libs the model links against. |
| `PYTHON` | `python` | Interpreter used for `enso-python-develop`. |
| `SIMB_CONDA_CHANNEL` | `-c https://conda.simbricks.io/latest` | Channel searched by `conda build` for external SimBricks deps. |
| `OUTPUT_FOLDER` | *(unset)* | If set, passed to `conda build --output-folder`. |

`install-enso.sh` additionally honours `ENSO_REPO`, `ENSO_BRANCH` and `ENSO_DIR`.

## Using it in a virtual prototype

With the packages installed, the Ensō classes are imported from the shared `simbricks.components.enso`
namespace and wired up like any other SimBricks component:

```python
from simbricks.orchestration import system
from simbricks.orchestration.helpers import simulation as sim_helpers
from simbricks.components.qemu import simulation as qemu_sim
from simbricks.components.net.simulation import base as net_sim
from simbricks.components.enso import system as enso_sys
from simbricks.components.enso.simulation import behavioral as enso_sim

syst = system.System("Enso-Example")

host = enso_sys.EnsoLinuxHost(syst)
# Ensō installed into the `base` image, built when the run is prepared. For a
# prebuilt image instead: system.DistroDiskImage(syst, "enso")
host.add_disk(enso_sys.enso_image(syst))
host.add_disk(system.LinuxConfigDiskImage(syst, host))

nic = enso_sys.EnsoNIC(syst)   # no add_ipv4(): Ensō exposes no kernel netdev
host.connect_pcie_dev(nic)
host.add_app(enso_sys.EnsoEchoServer(host))

sim = sim_helpers.simple_simulation(
    syst,
    compmap={
        system.FullSystemHost: qemu_sim.QemuSim,
        enso_sys.EnsoNIC: enso_sim.EnsoNicSim,
        system.EthSwitch: net_sim.SwitchNet,
    },
)
```

A complete two-host experiment is in [`examples/enso_echo.py`](examples/enso_echo.py).

## Status and known issues

- **PCIe address.** `EnsoGen` does not pass `--pcie-addr` by default and lets `ensogen` find the device.
  QEMU assigns the BDF and it is not knowable from the orchestration side; set `EnsoGen.pcie_addr` if
  autodetection picks the wrong device.
- **Cached images and moving branches.** The image's content hash covers the branch *name*, not the commit
  it points at, so new upstream commits on `simbricks-24.04` do not invalidate a cached image. Pin a commit
  or drop the cache entry when you need to pick them up.
- **Image cleanup runs by default.** `PackerImage.cleanup` purges apt caches, truncates logs and runs
  `fstrim` after the layers, which the packer template this replaces did not. It only autoremoves orphaned
  packages, so Ensō's runtime dependencies survive; set `enso_img.cleanup = False` if an image misbehaves.
- **A recent `simbricks-qemu-sim-py` is required** — the build from 2026-09-07 or later, which takes the
  kernel from the disk image's boot artifacts. It is still version 0.5.1, only a newer build, so a version
  constraint will not pull it in; `conda update simbricks-qemu-sim-py` will.
- The image build has only been exercised locally. Remote runs need no input artifacts for it any more, but
  the runner does need packer, qemu and `xorriso`.

## Versioning

`conda-recipes/conda_build_config.yaml`'s `simbricks_version` is the single source of truth for the conda
package versions built here, and for the `==` pins between them (`sim-bm-bin` → `sim-bm-py` → `sys-py`). It
MUST stay in sync with the `version` in both `enso_sys_py/pyproject.toml` and
`enso_sim_bm_py/pyproject.toml`, which drive the versions of the built wheels. External dependencies (e.g.
`simbricks-lib`) are not tied to it; they carry their own `>=` bounds since they release independently.
