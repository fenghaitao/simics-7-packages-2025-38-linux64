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
from simmod.os_awareness import common
from simmod.os_awareness.interfaces import nodepath

class _Fmt:
    def __init__(self, val):
        self.val = str(val)
    def __len__(self):
        return len(self.val)

class Left(_Fmt):
    def fmt(self, width):
        return self.val + ' ' * (width - len(self))

class Right(_Fmt):
    def fmt(self, width):
        return ' ' * (width - len(self)) + self.val

def fmt_default(val):
    if isinstance(val, _Fmt):
        return val
    elif isinstance(val, int):
        return Right(val)
    else:
        return Left(val)

def node_tree(osa_obj, print_id, root_id):
    common.requires_osa_enabled(osa_obj)

    nt_query = common.get_node_tree_query(osa_obj)

    def get_tree(prefix_first, prefix_rest, node_id):
        kids = nt_query.get_children(node_id)
        id_str = ("%d:" % node_id) if print_id else ""
        fn = "[" + id_str + node_name(osa_obj, node_id) + "]"
        prefix_first += fn
        prefix_rest += ' ' * len(fn)
        if not kids:
            return [prefix_first]

        if len(kids) == 1:
            marker = '*' if kids[0] in active_nodes else u'─'
            return get_tree(prefix_first + u'──%s' % marker,
                            prefix_rest + '   ', kids[0])

        marker = '*' if kids[0] in active_nodes else u'─'
        tree = get_tree(prefix_first + u'─┬%s' % marker, prefix_rest + u' │ ',
                     kids[0])
        for kid in kids[1:-1]:
            marker = '*' if kid in active_nodes else u'─'
            tree += get_tree(prefix_rest + u' ├%s' % marker,
                             prefix_rest + u' │ ', kid)
        marker = '*' if kids[-1] in active_nodes else u'─'
        tree += get_tree(prefix_rest + u' └%s' % marker,
                         prefix_rest + '   ', kids[-1])
        return tree

    root_nodes = common.roots(osa_obj)
    if not root_nodes:
        return cli.command_return(message="No root nodes found")

    tree_lines = []
    root_found = False
    for rid in root_nodes:
        if (root_id is None or root_id == rid):
            root_found = True
            active_nodes = set()
            for cpu in osa_obj.processors:
                active_nodes.update(nt_query.get_current_nodes(rid, cpu))
            tree_lines += get_tree('', '', rid)

    if not root_found:
        return cli.command_return(message="Root node %d not found" % root_id)

    print_str = "\n".join(tree_lines)
    return cli.command_return(message=print_str)

def add_node_tree_cmd():
    cli.new_command(
        'node-tree', node_tree,
        [cli.arg(cli.flag_t, "-id"),
         cli.arg(cli.integer_t, 'root-id', '?', None)],
        cls='os_awareness', type=['Debugging'],
        doc_items=[("NOTE", "Intended for debugging")],
        see_also = ['<os_awareness>.active-node', '<os_awareness>.find',
                    '<os_awareness>.list', '<os_awareness>.node-info'],
        short='list software node tree',
        doc="""

Lists the node trees for an active software tracker for debugging purposes. In
the general case the first level node represents an operating system. The second
level nodes represent the kernel and the userspace of the OS. Further node
levels are tracker specific.

The <tt>-id</tt> argument specifies if node ids should be printed in the node
tree.

The <arg>root-id</arg> argument specifies if only that specific node tree should
be printed.

Active nodes will be indicated by the "*" character.

See document "Analyzer - User's Guide", chapter "OS Awareness Details".""")

def node_info(osa_obj, node_spec):
    common.requires_osa_enabled(osa_obj)

    try:
        spec = nodepath.parse_node_spec(node_spec)
    except nodepath.NodePathError as e:
        raise cli.CliError(str(e))

    nt_query = common.get_node_tree_query(osa_obj)
    nodes = []
    for root_id in common.roots(osa_obj):
        nodes += list(nodepath.find_all_nodes(osa_obj, root_id, spec))
    if not nodes:
        return cli.command_return(message="Found no matching nodes")

    for node_id in nodes:
        props = nt_query.get_formatted_properties(node_id)
        if not props:
            if not nt_query.get_node(node_id):
                return cli.command_return(
                    message="Invalid node id: %d" % node_id)
            return cli.command_return(
                message="Invalid formatter for node with id %d" % node_id)
        children = ("[" + ", ".join("%d" % child
                                    for child in nt_query.get_children(node_id))
                    + "]")
        parent = nt_query.get_parent(node_id)
        name = props.pop('name', None)
        try:
            path = canon_path(osa_obj, node_id)
        except nodepath.NodePathError as e:
            path = "none (%s)" % str(e)
        info = [('Name', name),
                ('Path', path),
                ('ID', node_id),
                ('Parent', parent),
                ('Children', children)]

        cli.print_info([(None, info + sorted(props.items()))])

def add_node_info_cmd():
    cli.new_command(
        'node-info', node_info, args=[cli.arg(nodepath.node_spec_t, "node")],
        cls='os_awareness', type=['Debugging'],
        see_also = ['<os_awareness>.active-node', '<os_awareness>.find',
                    '<os_awareness>.list', '<os_awareness>.node-tree'],

        short='print all properties of a software node',
        doc=("Prints the name and value of all properties of the given"
             " <arg>node</arg>."))

def node_find(osa_obj, node_spec, flag_unique, flag_raise, flag_id, root_id):
    common.requires_osa_enabled(osa_obj)

    try:
        spec = nodepath.parse_node_spec(node_spec)
    except nodepath.NodePathError as e:
        raise cli.CliError(str(e))

    matching_nodes = []
    for rid in common.roots(osa_obj):
        if (root_id is None or root_id == rid):
            matching_nodes += list(nodepath.find_all_nodes(osa_obj, rid, spec))

    if flag_unique and len(matching_nodes) != 1:
        error_msg = ("Unique match requested, but found %d matches."
                     % len(matching_nodes))
        if flag_raise:
            raise cli.CliError(error_msg)
        return cli.command_return(value=[], message=error_msg)

    if not matching_nodes and flag_raise:
        raise cli.CliError("No match found")

    if not matching_nodes:
        return cli.command_return(value=[], message="No matching nodes")

    if flag_id:
        msg = '\n'.join([str(x) for x in matching_nodes])
        return cli.command_return(value=matching_nodes, message=msg)
    paths = [canon_path_cli(osa_obj, n) for n in matching_nodes]
    return cli.command_return(value=paths, message='\n'.join(paths))

def add_node_find_cmd():
    cli.new_command(
        'find', node_find, args=[cli.arg(nodepath.node_spec_t, "node"),
                                 cli.arg(cli.flag_t, "-unique"),
                                 cli.arg(cli.flag_t, "-raise"),
                                 cli.arg(cli.flag_t, "-id"),
                                 cli.arg(cli.integer_t, "root-id", '?', None)],
        cls='os_awareness', type=['Debugging'],
        see_also = ['<os_awareness>.active-node', '<os_awareness>.list',
                    '<os_awareness>.node-info', '<os_awareness>.node-tree'],

        short='find a node',
        doc="""
Search for a node in the node tree. The find command takes a node specification
as input and from that finds all nodes matching the expression. By default the
matching nodes are represented with their node path specification. If this
command is run from the CLI the matching nodes will be printed on the console.
If this command is run from a script it will return a list with the result.

The <arg>node</arg> contains the node specification to use when searching for
matching nodes. This is backward compatible with the old system. If the
<arg>node</arg> argument is an integer only, it will be treated as a node id.
For more information about node specifications please see the <cite>Analyzer
User's Guide</cite>.

The <tt>-id</tt> parameter can be specified in order to identify the matched
nodes with their node id instead of with a node path.

The <tt>-unique</tt> parameter can be specified to only allow one matching node
to be found. If multiple matches are found, no matches at all will be listed.

The <tt>-raise</tt> can be used to specify that the command should raise a
CliError if no nodes are found. It can also be used in combination with the
<tt>-unique</tt> parameter to force an exception if multiple nodes matches the
node specification.

The <arg>root-id</arg> argument specifies if only nodes belonging to that
specific node tree should be searched for. Leaving this out will search all node
trees.""")

def pretty_prop(prop):
    if isinstance(prop, list):
        return ', '.join(map(pretty_prop, prop))
    else:
        return str(prop)

def node_to_nodepath_node(node_id, node, parent):
    return nodepath.NodePathNode(node_id, node, parent)

def node_name(osa_obj, node_id):
    nt_query = common.get_node_tree_query(osa_obj)
    try:
        return nodepath.node_path_element(
            common.get_osa_admin(osa_obj),
            node_to_nodepath_node(
                node_id, nt_query.get_node(node_id), None),
            force_name=True)
    except nodepath.NodePathError as e:
        raise cli.CliError(str(e))

def canon_path(osa_obj, node_id):
    try:
        node_trav = nodepath.NodeTraverse(osa_obj, node_id).get_nodepath_node()
    except nodepath.NodePathError as e:
        raise cli.CliError(str(e))
    return str(nodepath.node_path(osa_obj, node_trav))

def canon_path_cli(osa_obj, node_id):
    try:
        return canon_path(osa_obj, node_id)
    except nodepath.NodePathError as e:
        raise cli.CliError(str(e))

def active_node(osa_obj, flag_id, arg, node_spec):
    common.requires_osa_enabled(osa_obj)

    all_cpus = common.get_all_processors(osa_obj)
    cpu_type = ""
    if arg is None:
        cpus = [cli.current_cpu_obj()]
        cpu_type = "current"
    else:
        (t, v, name) = arg
        if name == "-all":
            cpus = all_cpus
        else:
            cpus = [v]
            cpu_type = "specified"

    if cpu_type and cpus[0] not in all_cpus:
        # TODO: How to find the machine configuration name?
        raise cli.CliError(
            "The %s cpu (%s) does not belong to this machine"
            " configuration (%s). Use '-all' to list active nodes for"
            " all processors belonging to this machine configuration"
            % (cpu_type, cpus[0].name, common.get_top_obj(osa_obj).name))

    def find_common_parent(bases, nodes):
        for node in nodes:
            parent = node
            while True:
                parent = nt_query.get_parent(parent)
                if parent == None:
                    break
                if parent in bases:
                    break
            if parent == None:
                bases.append(node)

    nt_query = common.get_node_tree_query(osa_obj)
    bases = []
    if node_spec:
        try:
            spec = nodepath.parse_node_spec(node_spec)
        except nodepath.NodePathError as e:
            raise cli.CliError(str(e))

        # Only keep the most parent node for the node_spec in each tree branch
        for root_id in common.roots(osa_obj):
            nodes = list(nodepath.find_all_nodes(osa_obj, root_id, spec))
            find_common_parent(bases, nodes)
    else:
        bases = common.roots(osa_obj)

    def active_nodes_in_tree(cpu, root_cnt, root_id, active):
        root = (" (root_id=%d)" % root_id) if root_cnt > 1 else ""
        nodes = nt_query.get_current_nodes(root_id, cpu)
        if nodes and root_id in nodes:
            on = nodes[-1] if flag_id else canon_path_cli(osa_obj, nodes[-1])
            if on not in active:
                active[on] = "%s is active on %s%s" % (cpu.name, on, root)

    active = {}
    for cpu in cpus:
        for node_id in bases:
            active_nodes_in_tree(cpu, len(bases), node_id, active)

    if not active:
        return cli.command_return(message="No active processors", value=[])
    return cli.command_return(message="\n".join(list(active.values())),
                              value=list(active))

def add_active_node_cmd():
    cli.new_command('active-node',
                    active_node,
                    [cli.arg(cli.flag_t, "-id"),
                     cli.arg(
                         (cli.obj_t('processor', 'processor_info'), cli.flag_t),
                         ("cpu-name", "-all"), "?"),
                     cli.arg(nodepath.node_spec_t, 'node', "?", None)],
                    cls='os_awareness', type=['Debugging'],
                    see_also = ['<os_awareness>.find', '<os_awareness>.list',
                                '<os_awareness>.node-info',
                                '<os_awareness>.node-tree'],

                    short="list the active nodes",
                    doc="""
List the canonical node path for all leaf nodes that have an active processor.

The current processor is automatically selected unless a processor is given by
the <arg>cpu-name</arg> argument, or the <tt>-all</tt> argument is used to list
the active nodes for all processors that the os awareness system is aware of.

Node numbers are returned instead of the node paths, when the <tt>-id</tt>
argument is given.

A subset of the nodes can be selected with the <arg>node</arg> argument.""")

def list_cmd(osa_obj, root_id):
    common.requires_osa_enabled(osa_obj)

    nt_query = common.get_node_tree_query(osa_obj)
    def fmt_row(row, widths):
        return '  '.join(map(lambda x, w: fmt_default(x).fmt(w),
                             row, widths))
    def get_process_list(node_id):
        def get_list(prefix, title, rows):
            widths = [len(fmt_default(x)) for x in title]
            for (row, sub) in rows:
                assert len(row) == len(widths)
                for (i, x) in enumerate(row):
                    widths[i] = max(widths[i], len(fmt_default(x)))

            process_list = [prefix + fmt_row(title, widths)]
            for (row, sub) in rows:
                process_list.append(prefix + fmt_row(row, widths))
                if sub:
                    (sub_title, sub_rows) = sub
                    process_list.append(get_list(prefix + ' ' * 4, sub_title,
                                                 sub_rows))
            return process_list
        mapper = nt_query.get_mapper(node_id)
        if not mapper.iface.osa_mapper_query.get_process_list:
            raise cli.CliError(
                f"List support not implemented for {mapper.name}")
        res = mapper.iface.osa_mapper_query.get_process_list()
        if not isinstance(res, list) or len(res) != 2:
            raise cli.CliError(
                f"Badly formatted process list from {mapper.name}")
        (title, rows) = res
        return get_list('', title, rows)

    root_nodes = common.roots(osa_obj)
    if not root_nodes:
        return cli.command_return(message="No root nodes found")

    root_found = False
    for rid in root_nodes:
        if (root_id is None or root_id == rid):
            root_found = True
            list_to_print = "\n".join(get_process_list(rid))

    if not root_found:
        return cli.command_return(message="Root node %d not found" % root_id)
    return cli.command_return(message=list_to_print)

def add_list_cmd():
    cli.new_command(
        'list', list_cmd,
        args = [cli.arg(cli.integer_t, 'root-id', '?', None)],
        cls = 'os_awareness', type = ['Debugging'],
        see_also = ['<os_awareness>.active-node', '<os_awareness>.find',
                    '<os_awareness>.node-info', '<os_awareness>.node-tree'],
        short = 'list all processes/tasks',
        doc = """
Prints a list of all processes in the system (or tasks, or whatever the
currently active operating system calls them). Some additional information, such
as the ID of each process, is usually printed as well.

The <arg>root-id</arg> argument can be used to specify that only processes
belonging to that specific node tree should be listed.""")

def add():
    add_node_tree_cmd()
    add_node_info_cmd()
    add_node_find_cmd()
    add_active_node_cmd()
    add_list_cmd()
