# Copyright 2026 Max Planck Institute for Software Systems,
# National University of Singapore, Carnegie Mellon University,
# and SimBricks UG (haftungsbeschränkt)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The Ensō guest image: the SimBricks base image with Ensō installed into it.

    from simbricks.components.enso.system import enso_image

    host.add_disk(enso_image(system))
"""

from __future__ import annotations

import pathlib
import shlex
import typing as tp

from simbricks.imagebuild.packer.image import PackerImage
from simbricks.orchestration.system import disk_images

if tp.TYPE_CHECKING:
    from simbricks.orchestration.system import base as sys_base

_DATA = pathlib.Path(__file__).parent / "data"

ENSO_REPO = "https://github.com/crossroadsfpga/enso"
ENSO_BRANCH = "simbricks-24.04"
ENSO_DIR = "/root/enso"
DISK_SIZE = "16G"
BUILD_MEM_SIZE = "16G"
BUILD_CPUS = 4


def _script(name: str, env: dict[str, str]) -> str:
    """The packaged script @name with @env exported after its shebang."""
    lines = (_DATA / name).read_text().splitlines(keepends=True)
    exports = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in sorted(env.items()))
    return lines[0] + exports + "".join(lines[1:])


def enso_image(
    system: sys_base.System,
    enso_repo: str = ENSO_REPO,
    enso_branch: str = ENSO_BRANCH,
    enso_dir: str = ENSO_DIR,
) -> PackerImage:
    """The SimBricks ``base`` image with Ensō installed into it.

    Built with packer on the runner while the simulation is prepared; cached
    across runs with ``simbricks-run --image-cache-dir``.

    @enso_repo, @enso_branch and @enso_dir are exported into the install script
    and are part of the image's content hash. @enso_dir has to match the
    EnsoLinuxHost this image is attached to.

    The result is an ordinary PackerImage; ``cleanup``, ``accelerator`` etc.
    can be set on it.
    """
    image = PackerImage(system, disk_images.DistroDiskImage(system, "base"))
    image.disk_size = DISK_SIZE
    image.mem_size = BUILD_MEM_SIZE
    image.cpus = BUILD_CPUS
    image.run_script_str(
        "install-enso.sh",
        _script(
            "install-enso.sh",
            {"ENSO_REPO": enso_repo, "ENSO_BRANCH": enso_branch, "ENSO_DIR": enso_dir},
        ),
    )
    return image
