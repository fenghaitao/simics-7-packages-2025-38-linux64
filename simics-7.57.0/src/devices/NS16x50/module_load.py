# © 2010 Intel Corporation
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

def get_ascii(c):
    if len(repr(chr(c))) == 3:
        return chr(c)
    else:
        return c

def pretty_port(dev):
    import simics
    if isinstance(dev, simics.conf_object_t):
        return "%s" % dev.name
    elif isinstance(dev, list):
        return "%s:%s" % (dev[0].name, dev[1])
    else:
        return "none"

def get_info(obj):
    return [(None,
             [("Connected to", pretty_port(obj.console)),
              ("Transmit interval", "%d ns" % obj.xmit_time),
              ("Interrupt device", pretty_port(obj.irq_dev)),
              ("Interrupt level", obj.irq_level),
              ("xmit_time (ns)", obj.xmit_time)])]

def get_status_165(obj):
    divisor = (obj.regs_drm<<8) + obj.regs_drl
    stop_bits = 1
    if (obj.regs_lcr & 2**2):
        if ((obj.regs_lcr & (2**0 + 2**1)) == 0):
            stop_bits = 1.5
        else:
            stop_bits = 2

    return [(None,
             [("transmit FIFO", tuple(map(get_ascii, obj.xmit_fifo))),
              ("receive FIFO",  tuple(map(get_ascii, obj.recv_fifo))),
              ("stop bits", stop_bits),
              ("enable parity", obj.regs_lcr & 2**3 > 0),
              ("even parity", obj.regs_lcr & 2**4 > 0),
              ("stick parity", obj.regs_lcr & 2**5 > 0),
              ("number of data bits", (obj.regs_lcr & (2**0 + 2**1)) + 5),
              ("divisor", divisor)])]

def get_status_164(obj):
    return [(None,
             [("transmit holding", "empty" if obj.xmit_buffer == -1 else obj.xmit_buffer),
              ("receive buffer", "empty" if obj.recv_buffer == -1 else obj.recv_buffer)])]

cli.new_info_command('NS16450', get_info)
cli.new_info_command('NS16550', get_info)
cli.new_status_command('NS16550', get_status_165)
cli.new_status_command('NS16450', get_status_164)
