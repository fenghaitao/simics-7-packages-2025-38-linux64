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


import simics
import cli

# Return an arbitrary recorder from the given cell, or None if no instantiated
# recorder was found in that cell.
def get_one_recorder_from_cell(cell):
    for o in simics.SIM_object_iterator_for_class("recorder"):
        # ignore (manually created) recorders without queue
        if o.queue and o.queue.cell == cell:
            return o
    return None

# Generate the name of an auto-created recorder based on the cell it belongs to
def new_recorder_name(cell):
    prefix = (cell.name + "_") if cell else ""
    name = cli.get_available_object_name(prefix + "rec")
    return name

# Return a recorder to use in a specified cell. If no recorder exists, one
# will be created. The function will raise SimExc_General if the cell argument
# is not a cell object or if there is no clock associated with it.
def find_recorder(cell):
    if cell.classname != "cell":
        raise simics.SimExc_General("Not a cell")
    if not cell.current_cycle_obj:
        raise simics.SimExc_General("No clock found in selected cell")
    suitable_recorder = get_one_recorder_from_cell(cell)
    if not suitable_recorder:
        suitable_recorder = simics.SIM_create_object(
            "recorder", new_recorder_name(cell),
            [['queue', cell.current_cycle_obj]])
    return suitable_recorder
