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


import ast
import os
import comp
import pyobj
import simics
import cli
import component_commands

class FrameworkException(Exception): pass

# Our old Python 2.7 generated .params file may have a 'L' suffix to indicate
# long integers. In Python 3 we do not have long integers. Therefore the
# literal_eval will get a syntax error when parsing them. In order to support
# old params files we try to fix them by removing the 'L' suffix. This is best
# effort only.
def literal_eval_py2_compatible(s):
    try:
        return ast.literal_eval(s)
    except SyntaxError as e:
        split_lines = s.splitlines()
        prefix_lines = split_lines[0:e.lineno - 1]
        suffix_lines = split_lines[e.lineno:]
        faulty_line = split_lines[e.lineno - 1]
        if (e.offset >= 2
            and faulty_line[e.offset] == 'L'
            and faulty_line[e.offset - 1] in '0123456789'):
            updated_line = faulty_line[0:e.offset] + faulty_line[e.offset+1:]
            new_params_string = "\n".join(
                prefix_lines + [updated_line] + suffix_lines)
            return literal_eval_py2_compatible(new_params_string)
        raise

def set_parameters(tracker_comp, params):
    if not hasattr(tracker_comp.iface, 'osa_parameters'):
        raise FrameworkException(
            f'Tracker {tracker_comp.name} does not support parameters')
    (ok, msg) = tracker_comp.iface.osa_parameters.set_parameters(params)
    if not ok:
        raise FrameworkException(msg)

def load_parameters_file(filename):
    with open(filename, 'r') as f:
        s = f.read()
        if s.startswith('# -*- Python -*-'):
            try:
                (tracker, settings) = literal_eval_py2_compatible(s)
            except SyntaxError as e:
                raise FrameworkException(str(e))
            return [tracker, settings]
        else:
            raise FrameworkException('Unknown file format')

def save_parameters_file(filename, tracker, settings, overwrite):
    if os.path.exists(filename) and not overwrite:
        raise FrameworkException("The file already exists: %s" % filename)

    with open(filename, 'w') as f:
        f.write('# -*- Python -*-\n' + repr([tracker, settings]) + '\n')

def parameters_from_file(filename):
    f = simics.SIM_lookup_file(filename)

    if f is None:
        raise cli.CliError("Unable to open settings file (%s)" % filename)
    try:
        return load_parameters_file(f)
    except FrameworkException as e:
        raise cli.CliError("Failed to read settings file (%s): %s"
                           % (filename, e))
    except IOError as e:
        raise cli.CliError("Failed to open settings file (%s): %s"
                           % (filename, e))


def instantiate_component(obj):
    all_cmps = set([obj])
    def rec_find_cmps(obj):
        for o in obj.iface.component.get_slot_objects():
            if (isinstance(o, simics.conf_object_t)
                and hasattr(o.iface, 'component')):
                all_cmps.add(o)
                rec_find_cmps(o)
    rec_find_cmps(obj)

    try:
        component_commands.instantiate_cmd(False, list(all_cmps))
    except cli.CliError as ex:
        raise FrameworkException(str(ex))

def set_params_and_register_child(obj, parameters, parent_cmp, *extra_args):
    if parameters:
        set_parameters(obj, parameters)

    # Register the child last as the references from the parent to
    # the child prevents deletion.
    parent_cmp.object_data.register_child(obj, *extra_args)

def is_component(obj):
    return hasattr(obj.iface, 'component')

def insert_tracker(parent_cmp, name, tracker_class_name, parameters,
                   *extra_args):
    (osa_admin, tracker_domain, mapper_domain) = (
        parent_cmp.object_data.get_parents())
    child_name = '%s.%s' % (parent_cmp.name, name)
    try:
        tracker_class = simics.SIM_get_class(tracker_class_name)
        obj = simics.SIM_create_object(tracker_class, child_name,
                                       [['osa_admin', osa_admin],
                                        ['tracker_domain', tracker_domain],
                                        ['mapper_domain', mapper_domain]])
    except simics.SimExc_General as ex:
        raise FrameworkException("Failed creating tracker %s: %s"
                                 % (child_name, ex))

    try:
        if is_component(obj):
            instantiate_component(obj)
        set_params_and_register_child(obj, parameters, parent_cmp, *extra_args)
    except FrameworkException as ex:
        try:
            simics.SIM_delete_object(obj)
        except simics.SimExc_General as del_ex:
            raise FrameworkException(
                "Cleanup of '%s' failed: %s. Original problem: %s"
                % (child_name, del_ex, ex))
        raise
    return obj

class tracker_base_common(pyobj.ConfObject):
    _do_not_init = object()
    _no_new_command = object()
    _no_create_command = object()

    class osa_admin(pyobj.SimpleAttribute(None, 'o',
                                          simics.Sim_Attr_Required
                                          | simics.Sim_Attr_Internal)):
        """OSA Administrator. Internal."""

    class tracker_domain(pyobj.SimpleAttribute(None, 'o',
                                               simics.Sim_Attr_Required
                                               | simics.Sim_Attr_Internal)):
        """Tracker Domain. Internal."""

    class mapper_domain(pyobj.SimpleAttribute(None, 'o',
                                               simics.Sim_Attr_Required
                                               | simics.Sim_Attr_Internal)):
        """Mapper Domain. Internal."""

    class osa_tracker_component(pyobj.Interface):
        def get_tracker(self):
            return self._up.get_tracker()

        def get_mapper(self):
            return self._up.get_mapper()


class tracker_composition(tracker_base_common):
    """This is a base class when creating a tracker composition, which is an
       object that specifies what tracker and mapper to include."""
    _do_not_init = object()
    _no_new_command = object()
    _no_create_command = object()

    def _finalize(self):
        if not simics.SIM_is_restoring_state(self.obj):
            self.add_objects()

class tracker_comp(tracker_base_common, comp.StandardComponent):
    """This is a base class for legacy tracker components, based on Simics
       component system."""

    # Tracker components should be created by using the 'insert-tracker'
    # command and should have no create- or new- component commands.
    _no_new_command = object()
    _no_create_command = object()

    # Trackers that implement a tracker component that inherits from this class
    # should register its tracker component when loading the module.
    _do_not_init = object()

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
