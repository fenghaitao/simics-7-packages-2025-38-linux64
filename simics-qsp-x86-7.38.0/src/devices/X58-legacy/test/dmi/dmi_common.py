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


# dmi_common.py
#

import os, sys
sys.path.append(os.path.join("..", "vtd"))

from vtd_tb import *

class io_reg_offsets:
    config_address = 0xCF8
    config_data    = 0xCFC

def conf_addr_to_pci_addr(conf_addr):
    return ((conf_addr & 0x8fff00) * 0x10) + (conf_addr & 0xff)

def int_to_bytes(val, num_bytes):
    return tuple([(val & (0xff << pos*8)) >> pos*8 for pos in range(num_bytes)])

def bytes_to_int(list_bytes):
    result = 0
    for i in range(len(list_bytes)):
        result = result + (list_bytes[i] << i*8)
    return result
