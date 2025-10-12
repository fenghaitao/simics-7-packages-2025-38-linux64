# © 2020 Intel Corporation
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

def update_output_line(obj):
    assert obj.build_id < 6063

    # attribute introduced in 6.0.51
    if obj.build_id >= 6059:
        # Ignore obscure characters
        obj.output_line = tuple(obj.output_line.encode('utf-8', 'ignore'))

uc.SIM_register_class_update(6063, "graphcon",
                             update_output_line)

def external_connection_attributes(obj):
    if hasattr(obj, 'new_vnc_port_if_busy'):
        obj.tcp.new_port_if_busy = obj.new_vnc_port_if_busy
        delattr(obj, 'new_vnc_port_if_busy')
    if hasattr(obj, 'vnc_port'):
        obj.tcp.port = obj.vnc_port
        delattr(obj, 'vnc_port')
    if hasattr(obj, 'vnc_unix_socket'):
        obj.unix_socket.socket_name = obj.vnc_unix_socket
        delattr(obj, 'vnc_unix_socket')
    if hasattr(obj, 'vnc_use_ipv4'):
        conf.sim.force_ipv4 = obj.vnc_use_ipv4
        delattr(obj, 'vnc_use_ipv4')

uc.SIM_register_class_update(7000, "graphcon", external_connection_attributes)
