# © 2024 Intel Corporation
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

class_name = 'i_counter'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    sim = simics.SIM_get_object('sim')
    nid = [n for n in sim.notifier_list if n[1] == obj.notifier_id][-1][0]
    return [("",
             [("Notifier used", nid)]),
            ("Clock configuration", 
              [("Standard clock", (simics.SIM_object_clock(obj)).name),
              ("Picosecond clock", (simics.SIM_picosecond_clock(obj)).name)])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    rv = [("Event interval", f"{obj.bank.regs.event_interval} processor cycles"),
          ("Status", "Running" if obj.bank.regs.start_stop != 0 else "Stopped")]
    if rv[1][1] == "Running":
        evs = obj.queue.iface.cycle.events()
        cycles_left = [ ev for ev in evs if ev[0] == obj ][-1][2]
        rv+= [("Next event in", cycles_left)]
    return [("Event status:",
             rv),
            ("Counter state:",
             [("Counter value", obj.bank.regs.event_counter),
              ("Time in picoseconds", f"{obj.bank.regs.time_ps:_}")])]

cli.new_status_command(class_name, get_status)
