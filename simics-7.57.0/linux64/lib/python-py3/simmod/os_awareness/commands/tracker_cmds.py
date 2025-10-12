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
from simmod.os_awareness import framework

class OSAControl:
    def __init__(self, obj):
        self.obj = obj
        self.initstr = "CLI"
        self.obj_data = obj.object_data
    def get_req_id(self):
        return self.obj_data.enable_req_id
    def set_req_id(self, value):
        self.obj_data.enable_req_id = value
    def what(self):
        return "OSA control"
    def is_enabled(self):
        return self.get_req_id() != None
    def set_enabled(self, enable):
        if enable:
            (ok, rid_or_msg) = self.obj.iface.osa_control_v2.request(
                self.initstr)
            if not ok:
                raise cli.CliError(rid_or_msg)
            self.set_req_id(rid_or_msg)
        else:
            self.obj.iface.osa_control_v2.release(self.get_req_id())
            self.set_req_id(None)
    def done(self):
        if ((not self.is_enabled())
            and (len(self.obj.requests) > 0)):
            nr_reqs = len(self.obj.requests)
            i = 0
            reqs_str = ""
            for (_, name) in self.obj.requests:
                if i == nr_reqs - 1:
                    reqs_str += name
                elif i == nr_reqs - 2:
                    reqs_str += "%s and " % (name,)
                else:
                    reqs_str += "%s, " % (name,)
                i += 1
            self.extra_msg = ("Note: The tracker is still active from the"
                              " following initiators: %s" % (reqs_str,))

def tracker_comp_expander(prefix):
    tracker_comps = set([c for c in cli.global_cmds.list_classes()
                         if c.endswith('_tracker_comp')])
    tracker_comps.update(set([
        c for c in simics.SIM_get_all_classes()
        if simics.SIM_c_get_class_interface(c, 'osa_tracker_component')]))
    return cli.get_completions(prefix, sorted(tracker_comps))

def add_insert_tracker_cmd(cmp_class, extra_args):
    '''Add insert-tracker command which inserts a child tracker in cmp_class.

    cmp_class is the Python class that implements the tracker
    component. extra_args are cli.new_command argument descriptors
    that describe extra arguments that the tracker component uses to
    decide in which sub-domain the tracker should be inserted. These
    are the extra arguments.

    The tracker component's Python class must implement several hook
    methods:

    get_parents: should return [osa_admin, tracker_parent, mapper_parent]

    check_args: check the extra arguments and raises a FrameworkException on
    errors.

    register_child: registers the created child tracker. Takes the
    child component object and the extra arguments.

    child_base_name: returns the default name the child tracker
    component should be given. The user can override this by
    specifying the name parameter to the command. The method takes the
    extra arguments.

    insert_cmd_extra_doc: optional. Returns a string with extra documentation
    for the insert-tracker command of the component. As the insert-tracker
    command can be extended with extra arguments any such arguments should
    be documented in a string returned by this command.
    '''
    assert hasattr(cmp_class, 'get_parents')
    assert hasattr(cmp_class, 'check_args')
    assert hasattr(cmp_class, 'register_child')
    assert hasattr(cmp_class, 'child_base_name')
    insert_cmd_doc = ''' Create and insert a new child tracker component.

    The tracker will be configured as a child tracker of this tracker.

    The <arg>tracker</arg> argument specifies the tracker component to be
    inserted.

    The optional <arg>parameters</arg> argument is used to set
    parameters for the inserted tracker. This should be an existing
    file with the configuration parameters for that tracker.

    The <arg>name</arg> argument can be used to specify the component
    name in the component hierarchy. If this argument is ignored a
    default component name set by the component will be used.

    '''
    if hasattr(cmp_class, 'insert_cmd_extra_doc'):
        insert_cmd_doc += cmp_class.insert_cmd_extra_doc()

    def insert_tracker_cmd(parent_cmp, tracker_class, params_file, name,
                           *extra_args):
        if not getattr(parent_cmp, 'instantiated', True):
            raise cli.CliError("%s is not instantiated" % (parent_cmp.name,))
        try:
            simics.SIM_get_class(tracker_class)
        except simics.SimExc_General:
            raise cli.CliError("Class not found '%s'" % (tracker_class,))

        try:
            parent_cmp.object_data.check_args(*extra_args)
        except framework.FrameworkException as ex:
            raise cli.CliError(str(ex))

        if not simics.SIM_c_get_class_interface(tracker_class,
                                                'osa_tracker_component'):
            raise cli.CliError('%s is not a tracker component'
                               % (tracker_class,))
        if params_file:
            parameters = framework.parameters_from_file(params_file)
        else:
            parameters = None
        if not name:
            name = parent_cmp.object_data.child_base_name(*extra_args)
        try:
            cmp = framework.insert_tracker(parent_cmp, name, tracker_class,
                                           parameters, *extra_args)
        except framework.FrameworkException as e:
            raise cli.CliError(str(e))
        return cli.command_return(value=cmp,
                                  message=('Created and inserted %s'
                                           % (cmp.name,)))

    cli.new_command('insert-tracker', insert_tracker_cmd,
                    ([cli.arg(cli.str_t, 'tracker',
                              expander = tracker_comp_expander),
                      cli.arg(cli.filename_t(exist=True), 'parameters', '?'),
                      cli.arg(cli.str_t, 'name', '?')]
                     + extra_args),
                    cls = getattr(cmp_class, 'classname', cmp_class.__name__),
                    short = 'insert a new child tracker',
                    doc = insert_cmd_doc)

def delete_tracker(obj):
    if obj.requests:
        clients = (client for [_, client] in obj.requests)
        raise cli.CliError("Can't delete tracker; %s is currently used by %s"
                           %  (obj.name, ", ".join(clients)))

    tracker_comp = obj.current_tracker
    if not tracker_comp:
        raise cli.CliError("No tracker inserted into %s" % obj.name)

    # Need to clear state to get rid of any possible references to the
    # tracker and mapper objects.
    (ok, err_msg) = obj.iface.osa_control_v2.clear_state()
    if not ok:
        raise cli.CliError("Could not clear framework state: %s" % err_msg)

    obj.object_data.unregister_child(tracker_comp)
    # This should not fail. If it does someone has an illegal
    # reference into the tracker or one of its subobjects or a part of
    # the tracker component does not support deletion, which is not
    # allowed.
    simics.SIM_delete_object(tracker_comp)

def add_delete_tracker_cmd(cls_name):
    cli.new_command(
        'delete-tracker', delete_tracker, [],
        short = "delete tracker component",
        cls = cls_name,
        see_also = ["<os_awareness>.insert-tracker"],
        doc = """
Delete the tracker component inserted into this software domain.

This deletes all of the sub-objects of the tracker component, including
any sub-trackers inserted under it. It will fail if there is no tracker
inserted or if OS Awareness is currently enabled for this software domain.""")

def add_enable_tracker_cmd(cls_name):
    # TODO: I have not seen other commands that use this variable globally.
    # Bind the enable command to a name so that we can call it from other
    # commands that need to enable the tracker.
    enable_tracker = cli.enable_cmd(OSAControl)

    cli.new_command(
        'enable-tracker', enable_tracker, [],
        short = "enable software tracking",
        cls = cls_name,
        see_also = ["<os_awareness>.disable-tracker"],
        doc = """
Start tracking the software running on the target system.

This allows inspection of processes and tasks and other operating system
information for the software running on the target. It is also required to do
other tracking operations such as process debugging or analysis.""")

def add_disable_tracker_cmd(cls_name):
    cli.new_command(
        'disable-tracker', cli.disable_cmd(OSAControl), [],
        short = "stop using software tracking",
        cls = cls_name,
        see_also = ["<os_awareness>.enable-tracker"],
        doc = """
Stop tracking the software running on the target system.

When tracking is disabled, it is no longer possible to follow individual
processes and tasks. Note that if another user, such as Eclipse, has activated
the tracker, the tracker will remain active.""")

def add(comp_cls, cls_name):
    add_insert_tracker_cmd(comp_cls, [])
    add_delete_tracker_cmd(cls_name)
    add_enable_tracker_cmd(cls_name)
    add_disable_tracker_cmd(cls_name)
