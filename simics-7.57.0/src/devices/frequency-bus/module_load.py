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
import simics

device_name = "frequency_bus"

def get_status(obj):
    num, den = obj.current_output_freq
    prod = float(num) / float(den)
    return [(None,
             [("Current output frequency", "%d/%d = %g Hz"
               % (num, den, prod))])]

def get_info(obj):
    inputs = []
    for (name, unit, attr) in [("Frequency", " Hz", obj.frequency),
                               ("Scale factor", "", obj.scale_factor)]:
        # Urgh, unclean way of distinguishing conf objects from iterables
        if isinstance(attr, simics.conf_object_t):
            attr = [attr, None]
        [p, q] = attr
        if isinstance(p, int):
            inputs.append((name, "Fixed at %d/%d%s" % (p, q, unit)))
        elif q:
            inputs.append((name, "Taken from object %s, port %s" % (p, q)))
        else:
            inputs.append((name, "Taken from object %s" % p))

    def port_str(portname):
        if portname:
            return "connected to port %s" % portname
        else:
            return "connected"

    return [("Frequency inputs", inputs),
            ("Connected listeners",
             [(o.name, port_str(portname))
              for (o, portname) in obj.targets])]

cli.new_info_command(device_name, get_info)
cli.new_status_command(device_name, get_status)
