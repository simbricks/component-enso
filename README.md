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
| `guest/enso.pkr.hcl` | Packer template that installs Ensō into an existing guest image (option 1). |
| `guest/install-enso.sh` | The guest-side install step it runs — also usable as an image-builder component script (option 2). |
| `examples/enso_echo.py` | Runnable virtual prototype: EnsoGen against an Ensō echo server. |
| `Makefile` | Top-level driver for the builds below. |
| `.devcontainer/conda-build/` | VS Code dev container providing a ready-to-use conda build environment. |

## Conda packages

This repo produces three packages:

- **`simbricks-enso-sys-py`** — noarch Python package with the *system* components: `EnsoNIC`,
  `EnsoLinuxHost` and the `EnsoEchoServer` / `EnsoGen` applications. These describe *what* is being built
  and carry no simulator dependency, so a system description can be written (and shared) without installing
  the model.
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
`simbricks-orchestration` / `simbricks-utils` (runtime deps of the python packages) — are resolved
automatically from the public SimBricks conda channel (`https://conda.simbricks.io/latest`, wired into the
build via the Makefile's `SIMB_CONDA_CHANNEL`). You do **not** need to install them by hand.

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

Getting the software into an image is one guest-side script, [`guest/install-enso.sh`](guest/install-enso.sh):
it clones Ensō, hands off to Ensō's own `setup.sh`, and then installs the built module under
`/lib/modules/<kver>/extra` and runs `depmod`, so a plain `modprobe` finds it. Two constraints follow from
the kernel module: the image needs a kernel build tree at `/lib/modules/$(uname -r)/build`, and the script
must run **on the kernel the simulated hosts will boot** — an out-of-tree module is tied to the exact
kernel it was compiled against.

### Two ways to get an image

|  | 1. Specialize at run time | 2. Build your own image |
|---|---|---|
| Who builds it | `EnsoDiskImage`, on every run | you, once, up front |
| Template | this repo's [`guest/enso.pkr.hcl`](guest/enso.pkr.hcl) | `image.pkr.hcl` from [simbricks/image-builder](https://github.com/simbricks/image-builder) |
| Starts from | an existing SimBricks image (`base`) | a cloud image, or a base image built earlier |
| Cost | a full Ensō build per simulation run | none at run time |
| Image name in orchestration | stays `base` | yours, e.g. `enso` |
| Wired up as | `enso_sys.EnsoDiskImage(syst, guest_dir=...)` | `system.DistroDiskImage(syst, "enso")` |

Both exist to solve the same problem. Packer runs every provisioning stage in a *single* boot of the source
image, so `uname -r` inside a stage names the **source** image's kernel even after a different one has been
installed — the module would be built against the wrong kernel. Option 1 sidesteps that by booting the very
image the module will be loaded into; option 2 handles it with a reboot between the base stages and the
component scripts (see below).

Option 1 is what [`examples/enso_echo.py`](examples/enso_echo.py) does: nothing to prepare, at the price of
a packer run before every simulation. Prefer option 2 as soon as you run the same image more than a couple
of times, or on a runner where you would rather not have packer in the loop.

### Option 1 — specialize the base image at run time

`EnsoDiskImage` is a `DynamicDiskImage`: from `_prepare_format` — on the orchestration host, *before* the
simulation starts — it runs packer on [`guest/enso.pkr.hcl`](guest/enso.pkr.hcl), which boots the image the
hosts would otherwise run, executes `install-enso.sh` inside it, and writes the result out.

```python
enso_img = enso_sys.EnsoDiskImage(syst, guest_dir=".../component-enso/guest")
host.add_disk(enso_img)
```

That is all the wiring there is, and only one image name is in play. It derives from `DistroDiskImage` and
keeps the name of the image it installs into (`base` by default), so a host simulator booting an external
kernel finds it under `images/base/boot/` exactly as it would without Ensō — installing Ensō does not touch
the kernel. Only `path()` differs, pointing at the built image, which lands in the run's image dir; the
original is left untouched. Built once per run, however many hosts share it, and rebuilt on the next run.

Needs `packer` on `PATH` and the `base` image in the global input dir. For a **remote** runner, ship
`guest/` along by adding it to `instantiation.input_artifact_paths` (the example does); `EnsoDiskImage`
falls back to `input_artifacts/guest/` when the local path is absent. The runner then needs packer and the
`base` image too.

The same specialization by hand, without orchestration:

```sh
cd guest
packer init enso.pkr.hcl
packer build \
    -var source_image=/path/to/images/base/base \
    -var "scripts=[\"$PWD/install-enso.sh\"]" \
    -var name=enso -var output=/tmp/enso-image \
    enso.pkr.hcl                                   # -> /tmp/enso-image/enso
```

### Option 2 — build your own image

[simbricks/image-builder](https://github.com/simbricks/image-builder) builds a SimBricks image from a cloud
image and runs component install scripts as opaque guest-side stages, so `guest/install-enso.sh` plugs in
unchanged — it is exactly the kind of stage the harness expects.

This needs [image-builder#2](https://github.com/simbricks/image-builder/pull/2) (branch `incr-build`, open
at the time of writing). It splits provisioning into base stages (`BASE_SCRIPTS`: kernel, packages, boot
config, guest init) and component scripts (`EXTRA_SCRIPTS`), and **reboots the guest between the two**.
That reboot is what makes an Ensō stage possible at all: after it, `uname -r` is the kernel the base stages
installed, which is the kernel the simulated hosts boot, so the module is built and installed for the right
one.

So Ensō is one variable on image-builder's `make image`. Build its custom kernel first and use that as the
base stage, so the module is built against a kernel you control:

```sh
make kernel                          # custom no-initrd kernel -> output/kernel/

make image NAME=enso INPUT=output/kernel \
    BASE_SCRIPTS="kernel/install-kernel.sh scripts/install-base.sh scripts/configure-boot.sh scripts/install-guestinit.sh" \
    EXTRA_SCRIPTS=/path/to/component-enso/guest/install-enso.sh
```

`SOURCE_IMAGE` keeps image-builder's default cloud image, so there is nothing to pass. `install-kernel.sh`
replaces the default kernel stage and installs the `linux-image` / `linux-headers` debs `make kernel`
produced; the reboot then puts the guest on that kernel, and `install-enso.sh` runs on it. The image lands
in `output/enso/`. (image-builder can also stay on the distro kernel, or layer Ensō onto a base image it
built earlier — see its README.)

Install the result where orchestration looks for images — `images/<name>/` under the directory passed to
`simbricks-run --global-input-dir`. image-builder's output directory already has that layout:

```sh
cp -r output/enso <global-input-dir>/images/enso
# images/enso/enso        the qcow2 disk
# images/enso/boot/       vmlinuz / initrd / vmlinux, what host simulators boot
```

Then use it like any other distro image — no `EnsoDiskImage`, no packer at run time:

```python
enso_img = system.DistroDiskImage(syst, "enso")
host.add_disk(enso_img)
```

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

`guest/install-enso.sh` clones `ENSO_REPO` at `ENSO_BRANCH` (`crossroadsfpga/enso`, branch
`simbricks-24.04`) into `ENSO_DIR`, so pointing the image at your own work means overriding those. All
three are read from the **script's** environment inside the guest, which packer does not inherit from the
host — exporting them next to `simbricks-run` has no effect. Either edit the defaults in the script, or add
them to the `environment_vars` of the template you build with.

`make guest-install` runs the script directly, for when you are already inside the guest, and there the
environment does apply:

```sh
ENSO_REPO=https://github.com/me/enso ENSO_BRANCH=my-work make guest-install
```

With option 1 the image is rebuilt on every run, so an edit to the script lands in the next run; with
option 2, rebuild the image.

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
| `guest-install` | Run `guest/install-enso.sh`. Runs in the guest while the image is built. |
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

`guest/install-enso.sh` additionally honours `ENSO_REPO`, `ENSO_BRANCH` and `ENSO_DIR`.

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
# A prebuilt image containing the Ensō software (option 2). For the run-time
# build instead: enso_sys.EnsoDiskImage(syst, guest_dir=".../guest")
host.add_disk(system.DistroDiskImage(syst, "enso"))
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

- **Synchronization.** PR #138 reported that the model only worked with synchronization disabled on the
  network switch. Unsynchronized is the default in the current API, so the example works as-is, but running
  Ensō in a *synchronized* simulation has not been re-validated. Investigate before relying on timing
  results.
- **PCIe address.** `EnsoGen` does not pass `--pcie-addr` by default and lets `ensogen` find the device.
  QEMU assigns the BDF and it is not knowable from the orchestration side; set `EnsoGen.pcie_addr` if
  autodetection picks the wrong device.
- The run-time image build (option 1) shells out to `packer` and has only been exercised locally. It is
  meant to work for remote runs too, which will likely need the image cached somewhere shared rather than
  derived per runner — building the image up front (option 2) and installing it on the runner avoids the
  question entirely.
- Option 2 depends on [image-builder#2](https://github.com/simbricks/image-builder/pull/2), which is still
  open; until it lands, build from its `incr-build` branch.

## Versioning

`conda-recipes/conda_build_config.yaml`'s `simbricks_version` is the single source of truth for the conda
package versions built here, and for the `==` pins between them (`sim-bm-bin` → `sim-bm-py` → `sys-py`). It
MUST stay in sync with the `version` in both `enso_sys_py/pyproject.toml` and
`enso_sim_bm_py/pyproject.toml`, which drive the versions of the built wheels. External dependencies (e.g.
`simbricks-lib`) are not tied to it; they carry their own `>=` bounds since they release independently.
