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
import simics
from . import filter
import abc

# Each new connection will increment this counter
_connection_id = 0

# All connections active, as a dict, indexed by tool
_tool_connections = {}

# Called when the Core_Conf_Object_Pre_Delete triggers because an object
# is removed. If the object is associated to any established connections,
# remove these.
def _object_deleted(data, obj):

    for c in get_all_connections():
        if obj in [c._conn, c._tool, c._provider]:
            delete_connection(c)

simics.SIM_hap_add_callback("Core_Conf_Object_Pre_Delete", _object_deleted, None)

class connection_base(object, metaclass=abc.ABCMeta):
    __slots__ = ("_id", "_name", "_group_id", "_enabled")

    def __init__(self, name, group_id):
        self._id = -1                   # Illegal, must be updated later
        self._name = name
        self._group_id = group_id
        self._enabled = True

    def __repr__(self):
        return ("id=%d" % (self._id)
                + " name=%s" % (self._name)
                + " group_id=%d" % (self._group_id)
                + " enabled=%d" % (self._enabled))

    def get_id(self):
        return self._id

    def get_group_id(self):
        return self._group_id

    def get_name(self):
        return self._name

    # Could be overridden
    def get_enabled(self):
        return self._enabled

    # Could be overridden
    def get_connection_object(self):
        return None

    @abc.abstractmethod
    def get_disabled_string(self):
        assert 0

    @abc.abstractmethod
    def enable(self, filter_disable_mask):
        pass

    @abc.abstractmethod
    def disable(self, filter_disable_mask):
        pass

    @abc.abstractmethod
    def delete(self):
        pass

    @abc.abstractmethod
    def get_description(self):
        pass

# Class containing all the details regarding an instrumentation connection
class tool_connection(connection_base):
    __slots__ = ("_conn", "_tool", "_provider", "_desc",
                 "_aggregator", "_filter_objects")

    def __init__(self, tool_obj, group_id, provider_obj, conn_obj, desc):
        super(tool_connection, self).__init__(tool_obj.name, group_id)
        self._conn = conn_obj
        self._tool = tool_obj
        self._provider = provider_obj
        self._desc = desc
        self._filter_objects = []
        self._aggregator = simics.SIM_create_object(
            "instrumentation_filter_aggregator",
            self._conn.name + ".agg",
            [["dest", conn_obj]])

    def __repr__(self):
        return (super(tool_connection, self).__repr__() +
                (" conn=%s" % (self._conn.name)
                 + " tool=%s" % (self._tool.name)
                 + " provider=%s" % (self._provider.name)
                 + " desc=%s" % (self._desc)))

    def enable(self, source):
        self._aggregator.iface.instrumentation_filter_slave.enable(source)

    def disable(self, source):
        self._aggregator.iface.instrumentation_filter_slave.disable(source)

    def get_enabled(self):
        ifs = self._aggregator.iface.instrumentation_filter_status
        return len(ifs.get_disabled_sources()) == 0

    def get_slave(self):
        return self._aggregator

    def get_disabled_string(self):
        ''' Returns a string with all reasons why this connection
        is disabled. None if it is enabled.'''
        # Fetch all reasons why the connections is disabled from the MUX
        mux = self._aggregator
        sources = mux.iface.instrumentation_filter_status.get_disabled_sources()
        if not sources:
            return None
        # Return a list of the named sources
        return " & ".join(filter.get_filter_disabled_reasons(sources))

    def delete(self):
        # Inform all filters that this connection is being removed
        for f in self._filter_objects:
            filter.remove_filter_from_connection(self, f)

        simics.SIM_delete_object(self._aggregator)
        if not self._tool.iface.instrumentation_tool.disconnect:
            print(">" + self._tool.classname + "<")
        self._tool.iface.instrumentation_tool.disconnect(self._conn)


    def get_description(self):
        pos = get_connection_position(self._provider, self)
        # Get description from all connected filters
        fd = []
        for f in self._filter_objects:
            s = filter.short_filter_config(self, f)
            fd.append(s)
        filter_desc = ("filters: " + ",".join(fd)) if fd else ""

        return "connected to %s%s%s%s" % (
            self._provider.name,
            ":%d" % pos if pos >= 0 else "",
            (" " + self._desc) if self._desc else "",
            (" " + filter_desc) if filter_desc else "")

    def get_connection_object(self):
        return self._conn

    def get_connection_args(self):
        return self._desc

    def get_provider_object(self):
        return self._provider

    def add_filter(self, filter_obj):
        self._filter_objects.append(filter_obj)

    def remove_filter(self, filter_obj):
        self._filter_objects.remove(filter_obj)

    def get_filter_objects(self):
        return self._filter_objects

    def get_filters(self):
        fd = []
        for f in self._filter_objects:
            s = filter.short_filter_config(self, f)
            fd.append(s)
        return fd

    def get_tool_object(self):
        return self._tool

class cmd_connection(connection_base):
    __slots__ = ("_cmd_enable_fn", "_cmd_disable_fn", "_args",
                 "_disabled_sources")

    def __init__(self, id, cmd_name, group_id, cmd_enable_fn, cmd_disable_fn,
                 args):
        super(cmd_connection, self).__init__(cmd_name, group_id)
        self._cmd_enable_fn = cmd_enable_fn
        self._cmd_disable_fn = cmd_disable_fn
        self._args = args
        self._disabled_sources = set()

    def __repr__(self):
        return (super(cmd_connection, self).__repr__() +
                (" cmd_enable_fn=%s" % (self._cmd_disable_fn)
                 + " cmd_disable_fn=%s" % (self._cmd_disable_fn)
                 + " args=%s" % (self._args)))

    def enable(self, source):
        if source not in self._disabled_sources:
            return
        was_enabled = self._enabled
        self._disabled_sources.remove(source)
        self._enabled = not self._disabled_sources
        if was_enabled or not self._enabled:
            return
        self._cmd_enable_fn(self._args)

    def disable(self, source):
        was_disabled = not self._enabled
        self._disabled_sources.add(source)
        self._enabled = not self._disabled_sources
        if was_disabled or not self._enabled:
            return
        self._cmd_disable_fn(self._args)

    def get_disabled_string(self):
        if not self._disabled_sources:
            return None
        # Return a list of the named sources
        sources = self._disabled_sources
        return " & ".join(filter.get_filter_disabled_reasons(sources))

    def delete(self):
        pass # Nothing to be deleted

    def get_description(self):
        return ""

    def get_connection_object(self):
        return self._conn

def insert_connection(name, pyobj):
    '''Insert a new connection into the instrumentation framework'''
    global _connection_id
    _connection_id += 1
    pyobj._id = _connection_id

    conns = _tool_connections.get(name, set())
    conns.add(pyobj)
    _tool_connections[name] = conns

    return _connection_id

def get_all_connections():
    '''Get all registered instrumentation connection from the instrumentation
    framework.'''
    ret = []
    for t in _tool_connections:
        ret.extend(list(_tool_connections[t]))
    return ret

def get_named_connections(name):
    '''Get all registered instrumentation connection associated with a
    specific name.'''
    return list(_tool_connections.get(name, set()))

def delete_connection(c):
    '''Delete a connection from the instrumentation framework'''
    name = c.get_name()
    _tool_connections[name].remove(c)

def name_expander(str):
    return cli.get_completions(str, list(_tool_connections.keys()))

# TODO: move/rewrite
def get_connection_position(prov, connection):
    if not hasattr(prov.iface, "instrumentation_order"):
        return -1
    for i, c in enumerate(prov.iface.instrumentation_order.get_connections()):
        if c == connection.get_connection_object():
            return i
    return -1


# TODO
def add_instrumentation_commands():
    from . import groups

    def new_cmd_instrumentation(name, group_id, enable_fn, disable_fn, args):
        new = cmd_connection(_connection_id, name, group_id,
                             enable_foo, disable_foo, None)
        _ = insert_connection(name, new)

    def enable_foo(args):
        print("foo is enabled")
        return True

    def disable_foo(args):
        print("foo is disabled")
        return True

    def foo_cmd(group_name):
        gid = groups.cli_get_group_id(group_name)
        new_cmd_instrumentation("cmd:foo", gid, enable_foo, disable_foo, None)
        print("useful command, right?")

    cli.new_command("foo", foo_cmd,
                    args = [cli.arg(cli.str_t, "group", "?",
                                    expander = groups.group_expander)],
                    type = ["Instrumentation"],
                    short="foo",
                    doc="""Finally, a foo command!""")

# Should it be possible to have several groups per connection?
# Who controls the enabled status? The user, the tools?
# Should we distinguish 'disable' reasons, so a tool is only active
# when all sources says it is not disabled?

#add_instrumentation_commands()
