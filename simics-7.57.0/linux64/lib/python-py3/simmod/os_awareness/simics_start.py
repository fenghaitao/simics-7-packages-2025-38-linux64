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


import update_checkpoint as uc
import simics
import cli
from . import osa_update_checkpoint as osa_uc

def update_admin_for_object_and_children(objects, name, old_admin, new_admin):
    seen = set()
    updated = set()
    for (obj_name, obj) in objects.items():
        if not isinstance(obj, simics.pre_conf_object):
            continue
        if obj in seen:
            continue
        seen.add(obj)
        if not obj_name.startswith(name + '.'):
            continue
        for attr in vars(obj):
            attr_obj = getattr(obj, attr)
            if not isinstance(attr_obj, simics.pre_conf_object):
                continue
            if attr_obj == old_admin:
                setattr(obj, attr, new_admin)
                updated.add(obj)
    return updated

def new_osa_framework(objects):
    def find_coupled_admin(osa_comp, admins):
        for admin in admins:
            splits = admin.name.rsplit(".", 1)
            if len(splits) == 2 and splits[0] == osa_comp.name:
                return admin
        return None

    osa_comps = [c for c in uc.all_objects(objects, 'os_awareness')
                 if hasattr(c, 'top_component')]
    admins = uc.all_objects(objects, 'osa_admin')
    admin_to_osa = {}
    updated_with_new_admin = set()
    for osa_comp in osa_comps:
        admin = find_coupled_admin(osa_comp, admins)
        if admin is not None:
            for attr in ('next_node_id',
                         'trees',
                         'trackers',
                         'top_trackers',
                         'top_mappers',
                         'mappers',
                         'processors',
                         'bp_hits_before_removed_from_cache',
                         'processors_added'):
                if hasattr(admin,attr):
                    setattr(osa_comp, attr, getattr(admin, attr))
            osa_uc.remove_component_attributes(osa_comp)
            admin_to_osa[admin] = osa_comp
            updated_with_new_admin |= update_admin_for_object_and_children(
                objects, osa_comp.name, admin, osa_comp)
            del objects[admin.name]

    standalone_admins = set(admins) - set(admin_to_osa)
    for admin in standalone_admins:
        # Standalone objects of osa_admin class will be changed to objects of
        # os_awareness class. This is an unusual case for real targets.
        admin.__class_name__ = "os_awareness"
    return (list(admin_to_osa),
            list(set(osa_comps) | updated_with_new_admin | standalone_admins),
            [])

uc.SIM_register_generic_update(6172, new_osa_framework)

def create_osa(name, processor_names):
    try:
        processors = []
        if len(processor_names) > 0:
            for proc_name in processor_names:
                if not isinstance(proc_name, str):
                    raise cli.CliError("The 'processors' argument only accepts"
                                       " strings.")
                try:
                    obj = simics.SIM_get_object(proc_name)
                except simics.SimExc_General:
                    raise cli.CliError(f"The argument '{proc_name}' in"
                                       "'processors' is not a Simics object.")
                if not simics.SIM_object_is_processor(obj):
                    raise cli.CliError(f"The processors argument '{proc_name}'"
                                       " is not a processor.")
                processors.append(obj)
        obj = simics.SIM_create_object('os_awareness', name,
                                [['processors', processors]])
    except simics.SimExc_General as e:
        raise cli.CliError(e)
    return cli.command_return(
        message = f"Created OS awareness framework '{name}'", value = obj)

def new_create_os_cmd(prefix):
    cli.new_command(f'{prefix}-os-awareness', create_osa,
                    args = [cli.arg(cli.str_t, "name"),
                            cli.arg(cli.list_t, 'processors', '?', [])],
                    short = "create OS awareness framework",
                    doc = """
Create OS Awareness framework / software domain for adding trackers and
configuring cpus with. The framework provides interfaces for scripting and for
use by trackers.

<arg>name</arg>specifies the object name to create.

Use <arg>processors</arg> to specify the names of the processors.""")

for prefix in ('create', 'new'):
    new_create_os_cmd(prefix)
