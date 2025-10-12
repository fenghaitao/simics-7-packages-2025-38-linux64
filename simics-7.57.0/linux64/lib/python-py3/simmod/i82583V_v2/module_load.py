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
import sim_commands

class_name = "i82583V_v2"

enabled_tuple = ("Disabled", "Enabled")
yes_no_tuple = ("No", "Yes")

#
# ------------------------- LAN controller info/status -----------------------
#
def get_lan_info(obj):
    pci_info = sim_commands.get_pci_info(obj)
    # The value read from the registers is same as that read from the 6-byte
    # DA/SA in the ethernet frame header as a big-endian number
    addr_val = (obj.csr_ra_high[0] << 32) + obj.csr_ra_low[0]
    addr = list((addr_val >> n*8) & 0xff for n in range(6))
    lan_info = [
                ("LAN controller information",
                 [("Speed",
                   ("10Mbps","100Mbps","1000Mbps")[(obj.csr_ctrl >> 8) & 0x3]),
                  ("Duplex",
                   ("Half", "Full")[obj.csr_ctrl & 0x1]),
                  ("MAC address",
                   "%02X:%02X:%02X:%02X:%02X:%02X"
                    % (addr[0], addr[1], addr[2], addr[3], addr[4], addr[5])),
                 ]),
               ]
    return pci_info + lan_info

def get_lan_status(obj):
    pci_status = sim_commands.get_pci_status(obj)
    lan_status = [
        ("LAN controller status",
         [("Receive",
           enabled_tuple[(obj.csr_rctl >> 1) & 0x1]),
          ("Transmit",
           enabled_tuple[(obj.csr_tctl >> 1) & 0x1]),
          ]),
        ]

    return pci_status + lan_status

cli.new_status_command(class_name, get_lan_status)
cli.new_info_command(class_name, get_lan_info)
