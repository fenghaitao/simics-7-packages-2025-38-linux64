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
from simmod.os_awareness import common

def create_linux_task_graph(osa_obj, file_name, tracker, no_tg):
    def add_entity_ptrs_same_pid_tgid(mapping, entity, name):
        """Add both the next and prev pointer from a pointer group (e.g.
        children) if pid and tgid are the same (not threads)"""
        np = entity.get(name, [])
        if not np:
            return
        if entity.get('pid') != entity.get('tgid'):
            return
        if np[0]:
            mapping.setdefault((entity['addr'], np[0]), set()).add(
                "%s (n)" % name)
        if np[1]:
            mapping.setdefault((entity['addr'], np[1]), set()).add(
                "%s (p)" % name)

    def add_entity_ptrs_not_self(mapping, entity, name):
        """Add both the next and prev pointer from a pointer group (e.g.
        children) if they are not pointing to the entity itself."""
        np = entity.get(name, [])
        if not np:
            return
        if np[0] and np[0] != entity['addr']:
            mapping.setdefault((entity['addr'], np[0]), set()).add(
                "%s (n)" % name)
        if np[1] and np[1] != entity['addr']:
            mapping.setdefault((entity['addr'], np[1]), set()).add(
                "%s (p)" % name)

    def add_entity_to_dot(f, mapping, nodes, entity):
        """Add pointers of interesting based on an entity to the dot graph (this
        mapps to a Linux task)"""
        if no_tg and entity['tgid'] != entity['pid']:
            return
        addr = entity['addr']
        nodes[addr] = "0x%x, %s\\ntgid %d, pid %d" % (
            entity['addr'], entity['name'], entity['tgid'], entity['pid'])

        add_entity_ptrs_same_pid_tgid(mapping, entity, "tasks")
        if not no_tg:
            add_entity_ptrs_not_self(mapping, entity, "thread_group")

    def write_dot_header(f):
        f.write('digraph tasks {')
        f.write('\t node [shape="box"];\n\n')

    def write_nodes_to_dot(f, nodes):
        """Write the nodes representing a task struct to the output file"""
        for (addr, label) in nodes.items():
            f.write('\t%d [label="%s"];\n' % (addr, label))

    def write_mapping_to_dot(f, mapping):
        """Write the relationship between task structs to the output file"""
        for ((a,b), label) in mapping.items():
            f.write('\t%d -> %d [label = "%s"];\n\n' % (
                    a, b, ','.join(sorted(label))))

    def write_dot_footer(f, mapping, nodes):
        f.write('}\n')

    def write_dot(f, state_query):
        mapping = {}
        nodes = {}

        write_dot_header(f)

        entities = state_query.get_entities(tracker)
        if not entities:
            raise cli.CliError("No entities found")
        for (entity_id, entity) in entities.items():
            if (entity_id == 0):
                continue
            add_entity_to_dot(f, mapping, nodes, entity)
        write_nodes_to_dot(f, nodes)
        write_mapping_to_dot(f, mapping)
        write_dot_footer(f, mapping, nodes)

    state_query = common.get_osa_admin(osa_obj).iface.osa_tracker_state_query

    if tracker.classname == "linux_tracker":
        # The Linux tracker has a special attribute that will make the
        # tracker add additional information to the entities when set
        # to true.
        old_val = tracker.include_task_details
        tracker.include_task_details = True
    elif tracker.classname == "linux_analyzer":
        # The Linux analyzer has an attribute, which when written will
        # run an analyze and add matching entities.
        tracker.analyze = 1
    else:
        raise cli.CliError("Unsupported tracker '%s'" % (tracker.classname,))

    with open(file_name, "w+") as f:
        write_dot(f, state_query)

    if tracker.classname == "linux_tracker":
        tracker.include_task_details = old_val

def register_create_linux_task_graph_cmd(feature):
    cli.new_unsupported_command(
        "create-linux-task-graph", feature, create_linux_task_graph,
        [cli.arg(cli.filename_t(exist=False), 'file', '?', 'linux.dot'),
         cli.arg(cli.obj_t('Linux tracker or analyzer', 'osa_tracker_control'),
                 'tracker'),
         cli.arg(cli.flag_t, '-no-thread-group')],
        short = ("Create a graph showing relationships between Linux tasks"),
        iface = 'osa_component',
        doc = """
Write a dot file for the given <arg>tracker</arg>, representing the Linux task
struct relationships to <arg>file</arg> (defaulting to linux.dot).

Will include thread groups unless the <tt>-no-thread-group</tt> argument is
given. """)

def get_linux_tracker_params(sw):
    (params_valid, params_list) = sw.iface.osa_parameters.get_parameters(False)
    if not params_valid:
        return None

    (tracker_type, params) = params_list
    if tracker_type == "linux_tracker":
        return params
    return None

def insert_linux_analyzer(sw):
    common.requires_osa_disabled(sw)

    admin = common.get_osa_admin(sw)
    analyzer = simics.SIM_create_object("linux_analyzer",
                                        "%s.analyzer" % sw.name,
                                        [["node_tree", admin]])

    admin.top_trackers.append(analyzer)

    linux_params = get_linux_tracker_params(sw)
    if not linux_params:
        return
    analyzer.params = linux_params

def register_insert_linux_analyzer_cmd(feature):
    cli.new_unsupported_command(
        "insert-linux-analyzer", feature,
        insert_linux_analyzer, [],
        short = "Create and insert a Linux Analyzer object",
        iface = 'osa_component',
        doc = """
Create a Linux Analyzer object that is inserted as <software>.analyzer.

This will be included in top_trackers so that it is enabled when the tracker is
enabled. The framework needs to be disabled and re-enabled after this has been
inserted in order for the analyzer to be enabled.

The parameters will be copied from the Linux tracker. """)

def register():
    register_create_linux_task_graph_cmd('internals')
    register_insert_linux_analyzer_cmd('internals')
