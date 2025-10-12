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


import cli
import re

def plic_info(obj):
    obj_refs = cli.global_cmds.list_object_references(object=obj,
                                                      _include_ports=True,
                                                      max_len=None,
                                                      _only_inbound=True)
    r = re.compile(f"{obj.name}.port.IRQ\\[[0-9]+\\]$")
    sources = []
    for obj_ref in obj_refs:
        holder = obj_ref[0]
        attr = obj_ref[1]
        ref = obj_ref[2]
        if r.match(ref):
            sources.append(f"{ref} : {holder}.{attr}")
    sources = sorted(sources, key=lambda x: int(re.findall(r'\d+', x)[0], 10))

    return [(None,
             [("Interrupt sources", sources),
             ("Interrupt targets", [o for o in obj.attr.irq_dev if o]),
              ("Maximum threshold", obj.attr.max_threshold),
              ("Maximum priority", obj.attr.max_priority)])]

def plic_status(obj):
    inputs = [i for i in range(1024) if
              obj.attr.regs_raw[i // 32] & (1 << (i % 32))]
    pending = [i for i in range(1024) if
               obj.attr.regs_pending[i // 32] & (1 << (i % 32))]
    active = [i for i in range(1024) if
              obj.attr.regs_active[i // 32] & (1 << (i % 32))]

    def fmt_tgt(o):
        if hasattr(o, "name"):
            return o.name
        else:
            return "%s:%s" % (o[0].name, o[1])

    signals = []
    for (i, (intid, prio)) in enumerate(obj.attr.highest_pending):
        if intid == 0: continue
        signals.append((fmt_tgt(obj.attr.irq_dev[i]), (intid, prio)))

    return [(None,
             [("Raised Inputs", inputs),
              ("Pending Interrupts", pending),
              ("Active Interrupts", active),
              ("Raised Outputs", signals),])]

cli.new_info_command('riscv-plic', plic_info)
cli.new_status_command('riscv-plic', plic_status)

def clint_info(obj):
    return [(None,
             [("Frequency", "%f MHz" % obj.attr.freq_mhz),
              ("HARTs", obj.attr.hart)])]

def clint_status(obj):
    msip_state = ", ".join(["%d" % (obj.attr.regs_msip[i] & 1)
                          for i in range(len(obj.attr.hart))])
    mtip_state = ", ".join(["%d" % (obj.attr.regs_mtip[i] & 1)
                          for i in range(len(obj.attr.hart))])
    return [(None,
             [("msip state", msip_state),
              ("mtip state", mtip_state)])]


cli.new_info_command('riscv-clint', clint_info)
cli.new_status_command('riscv-clint', clint_status)
