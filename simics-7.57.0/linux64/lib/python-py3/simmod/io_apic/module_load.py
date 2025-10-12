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

def get_info(obj):
    return [ (None,
              [ ("APIC bus", obj.apic_bus) ]) ]

def redirection_description(dir_vect):
    ret = []
    for i in range(len(dir_vect)):
        entry = ("Pin %d" % i,
                 "0x%x (%s, %s, %s, %s, %s)"
                 % (dir_vect[i],
                    "masked" if (dir_vect[i] >> 16) & 1 else "unmasked",
                    "level" if (dir_vect[i] >> 15) & 1 else "edge",
                    "logical" if (dir_vect[i] >> 11) & 1 else "physical",
                    ("dest %d" % ((dir_vect[i] >> 56) & 0xff)),
                    ("vector %d" % (dir_vect[i] & 0xff))))
        ret.append(entry)
    return ret

def get_status(obj):
    return [ (None,
              [ ("APIC bus ID", "0x%x" % obj.ioapic_id),
                ("Register select", obj.register_select) ]),
             ("Redirection table",
              redirection_description(obj.redirection)) ]

cli.new_info_command('io-apic', get_info)
cli.new_status_command('io-apic', get_status)
