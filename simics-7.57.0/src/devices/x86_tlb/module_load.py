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

#
# ------------------------ info -----------------------
#

def calc_entries(tlb):
    return len(tlb) * len(tlb[0])

def calc_assoc(tlb):
    return len(tlb[0])

def get_info(obj):
    return [ (None,
              [ ("CPU", obj.cpu) ]) ]

cli.new_info_command("x86-tlb", get_info)

def access_to_string(access):
    r = "r" if access & simics.Sim_Access_Read else "-"
    w = "w" if access & simics.Sim_Access_Write else "-"
    x = "x" if access & simics.Sim_Access_Execute else "-"
    return r + w + x

def status_cmd(obj):
    entries_used = len(obj.tlb)
    print("%d entries used" % entries_used)
    if entries_used:
        print("------- LA ------- ------- PA ------- Supr User G PAT  MTRR SIZE")
        for entry in obj.tlb:
            print("0x%016x 0x%016x %-4s %-4s %s %-4s %-4s %-4s" % (
                entry[0],
                entry[1],
                access_to_string(entry[2]),
                access_to_string(entry[3]),
                "G" if entry[4] else "-",
                entry[5],
                entry[6],
                {4: "4k", 2*1024: "2M", 4*1024: "4M", 1024*1024: "1G"}[entry[7]]))

cli.new_command("status", status_cmd,
            [],
            short = "print status of the device",
            cls = "x86-tlb",
            doc = """
Print detailed information about the current status of the TLB object.<br/>
""")
