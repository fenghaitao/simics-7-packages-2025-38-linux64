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


import conf, simics, simicsutils
import os, platform, time
from comp import pre_obj

def get_machine_time(top):
    cpus = top.cpu_list
    return simics.SIM_time(cpus[0]) if cpus else 0.0

def objects_implementing_iface(iface):
    return list(simics.SIM_object_iterator_for_interface([iface]))

def create_checkpoint_info(comment, kind):
    '''Return a dictionary with newly created checkpoint metadata.'''
    host_type = simicsutils.host.host_type()
    tops = [x for x in objects_implementing_iface('component') if x.top_level]
    machines = [[x.system_info, x.class_desc, get_machine_time(x)]
                for x in tops]
    packages = [[name, version]
                for (_, name, _, version, _, _, host, *_)
                in conf.sim.package_info
                if host == host_type]
    if "USER" in os.environ:       # Linux
        user = os.environ["USER"]
    elif "USERNAME" in os.environ: # Windows
        user = os.environ["USERNAME"]
    else:
        user = None

    return {'comment': comment,
            'kind': kind,
            'date': time.ctime(),
            'host_type': host_type,
            'machines': machines,
            'prioritized_packages': conf.sim.prioritized_packages,
            'packages': packages,
            'user': user,
            'host_name': platform.node()}

def save_checkpoint_info(file, info):
    ci = pre_obj('checkpoint_info', 'checkpoint_info')
    for (k, v) in list(info.items()):
        setattr(ci, k, v)
    simics.CORE_write_pre_conf_objects(os.path.join(file, "info"), [ci],
                                       simics.Sim_Save_No_Gzip_Config)

def save_new_checkpoint_info(checkpoint, comment, kind):
    '''Save an info file for a checkpoint.

    Assumes checkpoint points to a valid bundle checkpoint.'''
    save_checkpoint_info(checkpoint,
                         create_checkpoint_info(comment, kind))

def load_checkpoint_info(path):
    """Loads information about a checkpoint and returns it as a dictionary.
    The path argument is the name of an existing checkpoint bundle.

    The checkpoint metadata is returned as a dictionary with the following keys:
    comment
      User comment describing the checkpoint.
    kind
      Kind of checkpoint file. Either "checkpoint" or "persistent-state".
    date
      Date of the checkpoint, set by Simics when the checkpoint is saved.
    host_type
      Host type Simics was running on when the checkpoint was taken.
    host_name
      Host machine Simics was running on when the checkpoint was taken.
    user
      Login name of the user taking the checkpoint.
    machines
      List of all machines in the checkpoint. For each machine, there
      is an instance-specific description, a machine class
      description and the time, in seconds, that the machine has run.
    packages, prioritized_packages
      Information about Simics packages at the moment the checkpoint was saved.

    Raises SimExc_General if the checkpoint info file is malformed.
    """

    info_file = os.path.join(path, "info")
    try:
        info = simics.VT_get_configuration(info_file)
    except simics.SimExc_General:
        # not an error, old checkpoints do not have any info
        if simics.SIM_get_verbose():
            print("Failed to load checkpoint info:", simics.SIM_last_error())
        return {}
    if len(info) != 1:
        raise simics.SimExc_General("Broken checkpoint info file")
    info_obj = list(info.values())[0]
    return dict((k, getattr(info_obj, k))
                for k in dir(info_obj)
                if not k.startswith('__') and k != 'object_id')

modifiable_keys = ['comment']

def update_checkpoint_info(path, newinfo):
    """Replace writable fields in the information attached to the checkpoint
    at 'path'. The checkpoint must be a bundle checkpoint with valid
    ancillary information. newinfo must be a dictionary with one item for each
    field in the information which should be updated. The key of the item names
    the field and the value of the item is the new value of the field.

    Attempts to update read-only or unknown fields will cause the update to
    fail. Returns true if the update was successful and false if the update
    failed.

    Currently the only writable field is the "comment" field.

    Raises SimExc_General if it fails to read the old checkpoint information, if
    you try to update a non-writable field or if the function fails to save the
    new checkpoint information.
    """

    if any((k not in modifiable_keys) for k in newinfo):
        raise simics.SimExc_General("Unmodifiable info key")
    info = load_checkpoint_info(path)
    if not info:
        raise simics.SimExc_General("No checkpoint info file")
    info.update(newinfo)
    save_checkpoint_info(path, info)
