# © 2022 Intel Corporation
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

def virt_bp_equal(a, b):
    (address_a, len_a, access_a, _, _, _) = a
    (address_b, len_b, access_b, _, _, _) = b
    if (address_a == address_b and len_a == len_b and access_a == access_b):
        return True
    return False

def virt_bp_combine(a, b):
    (address_a, len_a, access_a, cpu_a, hit_count_a, cids_a) = a
    (address_b, len_b, access_b, cpu_b, hit_count_b, cids_b) = b

    return [address_a, len_a, access_a, cpu_a.union(cpu_b),
            hit_count_a + hit_count_b, cids_a + cids_b]

def list_with_cpus_combined(break_points):
    if not break_points:
        return []
    new_list = []
    last = break_points[0]
    for bp in break_points[1:]:
        if virt_bp_equal(bp, last):
            last = virt_bp_combine(last, bp)
        else:
            new_list.append(last)
            last = bp
    new_list.append(last)
    return new_list

def access_string(access):
    if access == simics.Sim_Access_Read:
        return "read"
    if access == simics.Sim_Access_Write:
        return "write"
    if access == simics.Sim_Access_Execute:
        return "execute"
    return "unknown"

def list_virtual_breakpoints(osa_obj):
    breakpoints = {}
    for bps in osa_obj.virt_bps_with_listeners:
        (address, length, access, cpu, tracker, cid, hit_count) = bps
        # Add elements in the order we want to sort them
        breakpoints.setdefault(tracker, [])
        breakpoints[tracker].append([address, length, access, set([cpu]),
                                     hit_count, [cid]])

    for (tracker, breakpoints) in breakpoints.items():
        print("Virtual breakpoints planted by '%s':" % tracker.name)
        bp_list = list_with_cpus_combined(sorted(breakpoints))

        elements = []
        for bp in sorted(bp_list):
            (address, length, access, cpus, hit_count, cids) = bp
            elements.append(["0x%x" % address, length, access_string(access),
                             len(cpus), hit_count, cids])

        header = ["Address", "Length", "Access", "#CPUS", "#Hits",
                  "Cancel IDs"]
        cli.print_columns('lrrrrr', [header] + elements)

def add_list_virtual_breakpoints_cmds(feature):
    cli.new_unsupported_command('list-virtual-breakpoints', feature,
                                list_virtual_breakpoints, cls = 'os_awareness',
                                short = "List all planted virtual breakpoints"
                                " with an active listener",
                                doc = """
List all planted virtual breakpoints which is associated with an active
breakpoint listener. The breakpoints are sorted by their address""")

def add_unsupported(feature):
    add_list_virtual_breakpoints_cmds(feature)
