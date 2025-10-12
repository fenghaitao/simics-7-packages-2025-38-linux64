# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import conf
import update_checkpoint as uc

def update_scrollback_attribute_colours(obj):
    assert obj.build_id < 6007

    if obj.build_id < 5206 or obj.build_id >= 6000:
        sb = obj.scrollback_data
        # Convert to new colour attribute format
        new_cols = "".join(["%c%c%c%c" % (c & 0xf, 0, c >> 4, 0)
                            for c in sb[2]])
        sb[2] = tuple(ord(c) for c in new_cols)
        obj.scrollback_data = sb

uc.SIM_register_class_update(6007, "textcon",
                             update_scrollback_attribute_colours)

def update_text_attribute_colours(obj):
    assert obj.build_id < 6010

    if obj.build_id < 5212 or obj.build_id >= 6000:
        attribs = obj.text_attributes
        fg = attribs[1]
        bg = attribs[2]

        # Emulate old decode_vt_fg and decode_vt_bg
        if fg == 39:
            fg = 256
        elif fg >= 30 and fg <= 37:
            fg -= 30
        if bg == 49:
            bg = 257
        elif bg >= 40 and bg <= 47:
            bg -= 40

        attribs[1] = fg
        attribs[2] = bg
        obj.text_attributes = attribs

uc.SIM_register_class_update(6010, "textcon",
                             update_text_attribute_colours)

def update_esc_attrs(obj):
    assert obj.build_id < 6065

    # Attributes introduced in 6058
    if obj.build_id >= 6058:
        state = obj.esc_state
        state.insert(2, [False, False, ""])
        obj.esc_state = state

        flags = obj.filter_esc
        flags.insert(2, False)
        obj.filter_esc = flags

uc.SIM_register_class_update(6065, "textcon", update_esc_attrs)

def external_connection_attributes(obj):
    if hasattr(obj, 'new_telnet_port_if_busy'):
        obj.tcp.new_port_if_busy = obj.new_telnet_port_if_busy
        delattr(obj, 'new_telnet_port_if_busy')
    if hasattr(obj, 'telnet_port'):
        obj.tcp.port = obj.telnet_port
        delattr(obj, 'telnet_port')
    if hasattr(obj, 'telnet_unix_socket'):
        obj.unix_socket.socket_name = obj.telnet_unix_socket
        delattr(obj, 'telnet_unix_socket')
    if hasattr(obj, 'telnet_use_ipv4'):
        conf.sim.force_ipv4 = obj.telnet_use_ipv4
        delattr(obj, 'telnet_use_ipv4')

uc.SIM_register_class_update(7000, "textcon", external_connection_attributes)

# Attributes changed from string to data
def update_line_attrs(obj):
    assert obj.build_id < 7087

    for a in ("log_line", "output_line"):
        if hasattr(obj, a):
            l = getattr(obj, a)
            if isinstance(l, str):
                setattr(obj, a, tuple(l.encode('utf-8')))

uc.SIM_register_class_update(7087, "textcon", update_line_attrs)
