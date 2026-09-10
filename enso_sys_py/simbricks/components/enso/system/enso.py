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

from __future__ import annotations

import typing as tp

import typing_extensions as tpe

from simbricks.orchestration.system import base as sys_base
from simbricks.orchestration.system import nic
from simbricks.orchestration.system.host import app
from simbricks.orchestration.system.host import base as sys_host
from simbricks.utils import base as utils_base

if tp.TYPE_CHECKING:
    from simbricks.orchestration.instantiation import base as inst_base


class EnsoNIC(nic.SimplePCIeNIC):
    """
    The Ensō NIC.
    """

    def __init__(self, s: sys_base.System) -> None:
        super().__init__(s)


class EnsoLinuxHost(sys_host.LinuxHost):
    """
    A Linux host set up to drive an :class:`EnsoNIC`.

    On top of a plain Linux host this reserves hugepages, mounts ``hugetlbfs``
    and loads Ensō's kernel driver. The Ensō checkout itself is expected to be
    in the disk image, put there by :func:`.image.enso_image`.
    """

    def __init__(self, s: sys_base.System) -> None:
        super().__init__(s)
        # Ensō reserves several GiB of hugepages, so give the guest headroom.
        self.memory: int = 16 * 1024
        self.cores: int = 2

        self.enso_parent_dir: str = "/root"
        self.enso_name: str = "enso"

        self.nr_hugepages: int = 4096

        # Ensō's kernel driver, built into the image by install-enso.sh and
        # installed under /lib/modules/<kver>/extra, so it is modprobe'd by
        # name.
        self.enso_kmod: str = "intel_fpga_pcie_drv"
        self.enso_dev_node: str = "/dev/intel_fpga_pcie_drv"

    @property
    def enso_dir(self) -> str:
        return f"{self.enso_parent_dir}/{self.enso_name}"

    def prepare_pre_cp(self, inst: inst_base.Instantiation) -> list[str]:
        return [
            "mount -t proc proc /proc",
            "mount -t sysfs sysfs /sys",
        ] + super().prepare_pre_cp(inst)

    def prepare_post_cp(self, inst: inst_base.Instantiation) -> list[str]:
        # NOTE: LinuxHost.prepare_post_cp is bypassed on purpose. It walks every
        # PCIeHostInterface whose peer is an EthSimpleNIC/SimplePCIeNIC and
        # emits
        #     assert com._ip is not None
        #     ip link set dev ethN up
        #     ip addr add {com._ip}/24 dev ethN
        # An EnsoNIC is a SimplePCIeNIC but exposes no kernel netdev.
        cmds = sys_host.BaseLinuxHost.prepare_post_cp(self, inst)
        cmds += self._hugepage_cmds()
        cmds += self._enso_driver_cmds()
        return cmds

    def _hugepage_cmds(self) -> list[str]:
        """Equivalent of the hugepage section of Ensō's scripts/sw_setup.sh."""
        return [
            "mkdir -p /mnt/huge",
            'mount | grep -q " /mnt/huge " || mount -t hugetlbfs hugetlbfs /mnt/huge',
            f"echo {self.nr_hugepages} > "
            "/sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages",
        ]

    def _enso_driver_cmds(self) -> list[str]:
        """Load Ensō's kernel driver and make sure its device node exists.

        Replaces the driver loop of LinuxHost.prepare_post_cp, which we skip
        (see prepare_post_cp).
        """
        cmds: list[str] = []
        for driver in self.drivers:
            if driver[0] == "/":
                cmds.append(f"insmod {driver}")
            else:
                cmds.append(f"modprobe {driver}")

        node = self.enso_dev_node
        cmds += [
            "modprobe uio",
            f"modprobe {self.enso_kmod}",
            f"test -e {node} || mknod {node} c "
            f'$(grep -w {self.enso_kmod} /proc/devices | cut -f1 -d" ") 0',
            f"chmod 666 {node}",
        ]
        return cmds

    def toJSON(self) -> dict:
        json_obj = super().toJSON()
        json_obj["enso_parent_dir"] = self.enso_parent_dir
        json_obj["enso_name"] = self.enso_name
        json_obj["nr_hugepages"] = self.nr_hugepages
        json_obj["enso_kmod"] = self.enso_kmod
        json_obj["enso_dev_node"] = self.enso_dev_node
        return json_obj

    @classmethod
    def fromJSON(cls, system: sys_base.System, json_obj: dict) -> tpe.Self:
        instance = super().fromJSON(system, json_obj)
        instance.enso_parent_dir = utils_base.get_json_attr_top(json_obj, "enso_parent_dir")
        instance.enso_name = utils_base.get_json_attr_top(json_obj, "enso_name")
        instance.nr_hugepages = int(utils_base.get_json_attr_top(json_obj, "nr_hugepages"))
        instance.enso_kmod = utils_base.get_json_attr_top(json_obj, "enso_kmod")
        instance.enso_dev_node = utils_base.get_json_attr_top(json_obj, "enso_dev_node")
        return instance


class EnsoEchoServer(app.BaseLinuxApplication):
    """
    Ensō's bundled echo example, ``build/software/examples/echo``.
    """

    def __init__(self, h: EnsoLinuxHost) -> None:
        utils_base.has_expected_type(h, EnsoLinuxHost)
        super().__init__(h)
        self.threads: int = 1
        self.queues: int = 2
        self.cycles: int = 0

    def run_cmds(self, inst: inst_base.Instantiation) -> list[str]:
        host = self.host
        assert isinstance(host, EnsoLinuxHost)
        return [
            f"cd {host.enso_dir}",
            f"./build/software/examples/echo {self.threads} {self.queues} {self.cycles}",
        ]

    def toJSON(self) -> dict:
        json_obj = super().toJSON()
        json_obj["threads"] = self.threads
        json_obj["queues"] = self.queues
        json_obj["cycles"] = self.cycles
        return json_obj

    @classmethod
    def fromJSON(cls, system: sys_base.System, json_obj: dict) -> tpe.Self:
        instance = super().fromJSON(system, json_obj)
        instance.threads = int(utils_base.get_json_attr_top(json_obj, "threads"))
        instance.queues = int(utils_base.get_json_attr_top(json_obj, "queues"))
        instance.cycles = int(utils_base.get_json_attr_top(json_obj, "cycles"))
        return instance


class EnsoGen(app.BaseLinuxApplication):
    """
    Ensō's traffic generator, ``scripts/ensogen.sh``.
    """

    def __init__(self, h: EnsoLinuxHost) -> None:
        utils_base.has_expected_type(h, EnsoLinuxHost)
        super().__init__(h)
        # None selects Ensō's bundled sample capture, relative to enso_dir.
        self.pcap: str | None = None
        self.count: int = 10
        self.rate: int = 100  # Gbps
        self.pcie_addr: str | None = None

    def run_cmds(self, inst: inst_base.Instantiation) -> list[str]:
        host = self.host
        assert isinstance(host, EnsoLinuxHost)
        pcap = self.pcap
        if pcap is None:
            pcap = f"{host.enso_dir}/scripts/sample_pcaps/2_64_1_2.pcap"
        cmd = f"./scripts/ensogen.sh {pcap} {self.rate} --count {self.count}"
        if self.pcie_addr is not None:
            cmd += f" --pcie-addr {self.pcie_addr}"
        return [
            f"cd {host.enso_dir}",
            f"sleep 5",
            cmd,
            f"sleep 5",
        ]

    def toJSON(self) -> dict:
        json_obj = super().toJSON()
        json_obj["pcap"] = self.pcap
        json_obj["count"] = self.count
        json_obj["rate"] = self.rate
        json_obj["pcie_addr"] = self.pcie_addr
        return json_obj

    @classmethod
    def fromJSON(cls, system: sys_base.System, json_obj: dict) -> tpe.Self:
        instance = super().fromJSON(system, json_obj)
        instance.pcap = utils_base.get_json_attr_top_or_none(json_obj, "pcap")
        instance.count = int(utils_base.get_json_attr_top(json_obj, "count"))
        instance.rate = int(utils_base.get_json_attr_top(json_obj, "rate"))
        instance.pcie_addr = utils_base.get_json_attr_top_or_none(json_obj, "pcie_addr")
        return instance
