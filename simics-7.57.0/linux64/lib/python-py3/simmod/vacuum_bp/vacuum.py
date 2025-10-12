# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from blueprints import Builder, Namespace, State, ConfObject, blueprint
from blueprints.simtypes import MemMap
from blueprints.types import Config
from blueprints.params import params_from_config
from simmod.std_bp import state, console

class VacuumConfig(Config):
    clock_freq_mhz = 20
    ram_base = 0x10000000
    ram_size = 0x10000000

class VacuumState(State):
    mem: ConfObject = None
    mem_map: list[MemMap] = []
    uart = state.UARTConnectionState()

def uart_finalize(phys_mem):
    phys_mem.cli_cmds.write(address=0x1003, value=0x3, size=1)

# Blueprint adding a UART device in our bespoke way
def uart(builder: Builder, name: Namespace, data: VacuumState):
    data.uart.uart = builder.obj(name, "NS16550",
                                 xmit_time=0, console=data.uart.remote)
    data.mem_map.extend([MemMap(0x1000, name, 0, 0, 8)])
    builder.at_post_instantiate(name, uart_finalize, phys_mem=data.mem)
    # Hotplug support
    builder.expand(name, "con", state.uart, com=data.uart)

@blueprint(params_from_config(VacuumConfig))
def vacuum(builder: Builder, name: Namespace, config: VacuumConfig):
    # Follow convention and use a Queue state
    queue = builder.expose_state(name, state.Queue)
    data = builder.expose_state(name, VacuumState)
    # Set queue on all objects
    builder.obj(name, "blueprint-namespace", queue=queue.queue)
    # Add all main objects
    builder.obj(name.timer, "clock", freq_mhz=config.clock_freq_mhz)
    builder.obj(name.ram, "ram", image=name.ram.image)
    builder.obj(name.ram.image, "image", size=config.ram_size)
    data.mem = builder.obj(name.mem, "memory-space", map=data.mem_map)
    # Set state correctly
    queue.queue = name.timer
    data.mem_map.extend([MemMap(config.ram_base, name.ram, 0, 0,
                                config.ram_size)])
    # Expand other blueprints
    builder.expand(name, "uart", uart)
    builder.expand(name, "console", console.text_console, dev=data.uart)
