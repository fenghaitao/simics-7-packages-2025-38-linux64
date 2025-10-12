# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from blueprints import (
    OMIT_ATTRIBUTE, Builder, DefaultTarget, Config,
    MemMap, Namespace, ConfObject)
from .state import GFXConsoleConnectionState, PCIEFunction, PCIESlotConnectionState, PCIEDevice
import os

X58_IMAGES = "%simics%/targets/x58-ich10/images"

class AccelVGAParams(Config):
    vga_bios = ""
    "The VGA BIOS to use."

def accel_vga(bp: Builder, name: Namespace,
              params: AccelVGAParams,
              slot: PCIESlotConnectionState):
    import simics
    pci_bus = slot.bus
    gfx = bp.expose_state(name, GFXConsoleConnectionState)

    def round_up_2exp(i):
        return 0 if i == 0 else ((1 << (i - 1).bit_length()) - 1) + 1

    if params.vga_bios:
        path = simics.SIM_lookup_file(params.vga_bios)
        bios_size = os.stat(path).st_size if path else 0
        if bios_size == 0:
            bp.error(f"Missing VGA bios '{params.vga_bios}'")
        bios_map_size = round_up_2exp(bios_size)
        pci_bus.mem_map.append(
            MemMap(0xc0000, name.bank.pcie_config.expansion.rom, 0, 0, bios_map_size))
    else:
        bios_map_size = 1024

    bp.obj(name, "accel_vga_v2",
        pci_bus = pci_bus.bus,
        direct_map_space = name.vram_space,
        video_ram = name.vram,
        image = name.vram.image,
        memory_space = pci_bus.mem,
        expansion_rom_size = bios_map_size,
        console = gfx.console,
    )
    gfx.gfx_device = ConfObject(name.vga_engine)
    bp.obj(name.io, "port-space",
        map = [
            MemMap(0x1ce, name.bank.vbe_io, 0, 0, 2),
            MemMap(0x1cf, name.bank.vbe_io, 0, 2, 2),
            # GOP driver uses port 0x1d0 instead of 0x1cf
            MemMap(0x1d0, name.bank.vbe_io, 0, 2, 2),
        ] + [
            # IO_VGA
            MemMap(0x3b0 + i, name.vga_io, 0, 0x3b0 + i, 1) for i in range(0x30)
        ],
    )
    bp.obj(name.vram, "ram", image = name.vram.image)
    bp.obj(name.vram.image, "image", size = 0x1000000)
    bp.obj(name.vram_space, "memory-space",
        default_target = DefaultTarget(name.port.video_mem))

    pci_bus.mem_map.extend([
        MemMap(0xa0000, name.vram_space, 0, 0, 0x20000),
    ])
    pci_bus.io_map.extend([
        MemMap(0x1ce, name.io, 0, 0x1ce, 4),
        MemMap(0x3b0, name.io, 0, 0x3b0, 0x30),
    ])
    pci_bus.pcie_devices.append(PCIEDevice(slot.device, 0, name))
