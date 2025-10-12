# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from blueprints import Builder, ConfObject, Namespace, Port
from . import state

def sii3e132(bp: Builder, name: Namespace):
    "SATA PCIe card"
    sata = [bp.expose_state(name.sata@i, state.SATAConnectionState)
            for i in range(2)]

    for i in range(2):
        sata[i].controller = Port(name, f"sata_port[{i}]")
        bp.obj(name.sata@i, state.sata, sata=sata[i])

    slot = bp.read_state(name, state.PCIESlotConnectionState, allow_local=True)
    bp.expand(name, "con", state.pcie_device_slot,
              fn=state.PCIEFunction(0, name), slot=slot)
    bp.obj(name, "sii3132",
        pci_bus = slot.bus.bus,
        sata_device = [sata[0].device, sata[1].device] + [ConfObject()] * 30,
    )
