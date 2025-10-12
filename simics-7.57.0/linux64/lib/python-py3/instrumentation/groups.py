# © 2016 Intel Corporation
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

# Instrumentation groups are handled in a hash table with the
# name as hash, containing the group-nr
instrumentation_group_id = 0
instrumentation_groups = { None : 0 }  # unused group == id 0


def cli_get_group_id(name):
    '''Fetches the group number for a given group-name, raises CLI
    exception if the name is unknown.'''
    if name not in instrumentation_groups:
        raise cli.CliError("Unknown group name '%s'" % name)
    return instrumentation_groups[name]

# Exported functions from instrumentation-preview, can be removed
# later when this module is removed.
def get_groups():
    return instrumentation_groups

def set_group(name):
    global instrumentation_group_id
    instrumentation_group_id += 1
    instrumentation_groups[name] = instrumentation_group_id

def remove_group(name):
    del instrumentation_groups[name]

def get_group_name(id):
    for n in instrumentation_groups:
        if instrumentation_groups[n] == id:
            return n
    return None

def get_group_names():
    return [g for g in instrumentation_groups if g != None]

def group_expander(name):
    return cli.get_completions(name, get_group_names())
