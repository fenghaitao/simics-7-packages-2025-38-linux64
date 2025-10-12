# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import cli
import simics
from . import standard_pcie_switch_comp

standard_pcie_switch_comp.standard_pcie_switch_comp.register()

args_press_attention_button = [
    cli.arg(cli.uint64_t, "slot"),
]

doc_press_attention_button = """Press the attention button of a Downstream Port
Slot with index <arg>slot</arg> in the switch. This should be done for Hot-Plug
removal of a device connected to that port."""

doc_press_attention_button_short = "press the attention button of a Downstream Port"


def press_attention_button(obj, slot):
    if slot >= len(obj.sw.dsp):
        raise cli.CliError(
            f"Invalid slot index {slot}. Must be between 0-{len(obj.sw.dsp) - 1}"
        )
    obj.sw.dsp[slot].iface.pcie_hotplug_events.attention_button_pressed()


cli.new_command(
    "press-attention-button",
    press_attention_button,
    args_press_attention_button,
    cls="standard_pcie_switch_comp",
    doc=doc_press_attention_button,
    short=doc_press_attention_button_short,
)
