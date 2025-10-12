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


from . import connections
import cli

_filter_sources = {}     # Bit-number 0, 1, 2, 3 indexed by filter-name
_filter_source_count = 0 # Currently registered number of bits. Max 63

def get_filter_disabled_reasons(sources):
    '''Returns the associated filter names for all sources (disabled)
    in a value'''

    def _filter_for_bit(bit_num):
        for k in _filter_sources:
            if _filter_sources[k] == bit_num:
                return k
        assert 0  # A bit is set which has not been assigned with a name

    return [_filter_for_bit(s) for s in sources ]

def add_filter_to_connection(c, filter_obj):
    slave = c.get_slave()
    provider = c.get_provider_object()
    master_iface = filter_obj.iface.instrumentation_filter_master
    if master_iface.add_slave(slave, provider):
        c.add_filter(filter_obj)
        return True
    return False

def remove_filter_from_connection(c, filter_obj):
    slave = c.get_slave()
    provider = c.get_provider_object()
    filter_obj.iface.instrumentation_filter_master.remove_slave(slave, provider)
    c.remove_filter(filter_obj)

def short_filter_config(c, filter_obj):
    s = filter_obj.iface.instrumentation_filter_master.short_filter_config()
    if s:
        return "%s(%s)" % (filter_obj.name, s)
    else:
        return filter_obj.name

def attach_filter(tool_name, filter_obj, group_id):
    '''Register that a tool/cmd has a filter assigned.'''
    added = []
    # Register the filter to the connection
    for c in connections.get_named_connections(tool_name):
        # Only attach to connections with the correct group
        if group_id > 0 and c.get_group_id() != group_id:
            continue

        # Don't attach filter to connection already attached
        if filter_obj in c.get_filter_objects():
            continue

        ok = add_filter_to_connection(c, filter_obj)
        if ok:
            added.append(c)
        else:
            # Failed, remove the filters we already assigned
            for a in added:
                remove_filter_from_connection(a, filter_obj)
            raise cli.CliError("Error in filter assignment")
    return len(added)

def detach_filter(tool_name, filter_obj):
    '''Remove a filter from a tool/cmd'''

    for c in connections.get_named_connections(tool_name):
        remove_filter_from_connection(c, filter_obj)

@cli.doc('Python function to get hold of a unique filter id',
         module = 'instrumentation',
         doc_id = 'instrumentation_filter_python_api')
def get_filter_source(fname):
    '''For a given name, which could be the filter object name,
    return an unique number which identifies this filter.'''
    if fname in _filter_sources:
        return _filter_sources[fname]
    global _filter_source_count
    if _filter_source_count == 64:
        return -1    # Out of filter bits
    _filter_source_count += 1
    _filter_sources[fname] = _filter_source_count
    return _filter_sources[fname]

@cli.doc('Python function which removes a filter',
         module = 'instrumentation',
         doc_id = 'instrumentation_filter_python_api')
def delete_filter(filter_obj):
    '''Used by a filter when a filter object removes itself. Needed to
    keep the instrumentation framework consistent in regards of which
    filters that are associated with tools.'''

    for c in connections.get_all_connections():
        if filter_obj in c.get_filter_objects():
            remove_filter_from_connection(c, filter_obj)
