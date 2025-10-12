# © 2015 Intel Corporation
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
from . import partition_tracker_composition
partition_tracker_composition.partition_tracker_comp.register()

def get_partition_tracker_status(part_tracker):
    part_status = [(None, [("Enabled", part_tracker.enabled)])]
    for part in part_tracker.partitions:
        (part_id, guest, name, cpus) = part
        part_status.append([name, [("Partition ID", part_id),
                                   ("Guest object", guest),
                                   ("CPUs", cpus)]])
    return part_status

def get_partition_tracker_info(part_tracker):
    return [(None, [("Name", part_tracker.tracker_name),
                    ("Parent", part_tracker.parent)])]

def get_partition_mapper_status(part_mapper):
    part_status = [(None, [("Enabled", part_mapper.enabled)])]
    for part in part_mapper.partitions:
        (part_id, guest, name, guest_name, node_id, cpus, subs) = part
        part_status.append([name, [("Partition ID", part_id),
                                   ("Node ID", node_id),
                                   ("Guest object", guest),
                                   ("Guest name", guest_name),
                                   ("CPUs", cpus),
                                   ("Subscriptions", subs),]])
    return part_status

def get_partition_mapper_info(part_mapper):
    return [(None, [("Tracker", part_mapper.tracker),
                    ("Parent", part_mapper.parent)])]

def add_info_status():
    cli.new_status_command("partition_tracker", get_partition_tracker_status)
    cli.new_info_command("partition_tracker", get_partition_tracker_info)
    cli.new_status_command("partition_mapper", get_partition_mapper_status)
    cli.new_info_command("partition_mapper", get_partition_mapper_info)

add_info_status()
