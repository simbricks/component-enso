# MIT License
#
# Copyright (c) 2026 SimBricks
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Two Ensō hosts across an Ethernet switch: EnsoGen drives an echo server.

This is the modern port of the experiment from
https://github.com/simbricks/simbricks/pull/138.
"""

import pathlib

from simbricks.components.enso import system as enso_sys
from simbricks.components.enso.simulation import behavioral as enso_sim
from simbricks.components.net.simulation import base as net_sim
from simbricks.components.qemu import simulation as qemu_sim
from simbricks.orchestration import system
from simbricks.orchestration.helpers import instantiation as inst_helpers
from simbricks.orchestration.helpers import simulation as sim_helpers

syst = system.System("Enso-Echo")

GUEST_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "guest")
# The `base` image with Ensō installed into it. The install runs on the
# orchestration host before the simulation starts: packer boots `base`, runs
# guest/install-enso.sh inside it and writes the result into the run's image
# dir. It is rebuilt on every run.
enso_img = enso_sys.EnsoDiskImage(syst, guest_dir=GUEST_DIR)

# Alternatively, install Ensō out of band and use the result directly:
# enso_img = system.DistroDiskImage(syst, "enso")

server = enso_sys.EnsoLinuxHost(syst)
server.add_disk(enso_img)
server.add_disk(system.LinuxConfigDiskImage(syst, server))

server_nic = enso_sys.EnsoNIC(syst)
server.connect_pcie_dev(server_nic)
server.add_app(enso_sys.EnsoEchoServer(server))

client = enso_sys.EnsoLinuxHost(syst)
client.add_disk(enso_img)
client.add_disk(system.LinuxConfigDiskImage(syst, client))

client_nic = enso_sys.EnsoNIC(syst)
client.connect_pcie_dev(client_nic)

ensogen = enso_sys.EnsoGen(client)
ensogen.count = 1000
ensogen.wait = True
client.add_app(ensogen)

switch = system.EthSwitch(syst)
switch.connect_eth_peer_if(server_nic._eth_if)
switch.connect_eth_peer_if(client_nic._eth_if)

simulation = sim_helpers.simple_simulation(
    syst,
    compmap={
        system.FullSystemHost: qemu_sim.QemuSim,
        enso_sys.EnsoNIC: enso_sim.EnsoNicSim,
        system.EthSwitch: net_sim.SwitchNet,
    },
)

instantiation = inst_helpers.simple_instantiation(simulation)

# guest/ holds the packer template and the install script the image build needs,
# and its path is local to this machine. Ship it so a remote runner has it too:
# the client packs each entry flat, so the runner unpacks it to
# input_artifacts/guest/, which is where EnsoDiskImage looks when the local path
# is absent. A remote runner additionally needs packer and the `base` image.
instantiation.input_artifact_paths = [GUEST_DIR]

instantiations = [instantiation]
