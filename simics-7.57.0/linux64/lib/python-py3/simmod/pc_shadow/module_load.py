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


from cli import (
    Just_Left,
    new_command,
    new_info_command,
    print_columns,
)

def shadow_cmd(obj):
    r = [ [ "Base", "Read", "Write" ] ]
    read_write = ("PCI", "RAM")
    crs = obj.config_register
    shadow_start = 640
    for i in range(256):
        subrange = crs[i] & 0x3
        if subrange:
            r.append(["%x" % ((shadow_start + i * 2) * 1024),
                      read_write[subrange & 1],
                      read_write[subrange >> 1]])
    print_columns([Just_Left, Just_Left, Just_Left], r)
    print("All addresses not listed are forwarded to PCI")

new_command("status", shadow_cmd, [], cls = "pc-shadow",
            short = "device status",
            doc = """
Print the shadow RAM status for each 2kb region between 640kb and 1Mb.""")

def get_info(obj):
    return []

new_info_command('pc-shadow', get_info)
