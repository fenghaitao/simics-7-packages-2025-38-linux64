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


# Checkpoint updaters for Simics core and for anything else that isn't
# possible or practical to put in the gcommands for an individual module.



from update_checkpoint import *
from simics import *
import os
import re
import math

# Older versions of Simics only handled attribute integers in the
# range [0, 2**64 - 1], but values in the range [2**64 - 999, 2**64 - 1]
# were checkpointed as [-999, -1] (and converted back when the
# checkpoint was read). When the attribute integer range was increased
# to [-2**63, 2**64 - 1] (bug 16996), negative values in checkpoints
# started to correspond to negative attribute values.
#
# This updater rewrites integers in the range [-999, -1] to
# [2**64 - 999, 2**64 - 1], so that large integer values in older
# checkpoints will not suddenly end up negative. t888 tests that it works
# properly.
def fix_int_attr(v):
    # We save time here by noting that attribute values in the range
    # [-999, -1] are always Python-converted to int and not long, and
    # that values less than -999 do not occur in older checkpoints.
    if isinstance(v, int):
        if v < 0:
            v += 2**64
        return v
    elif isinstance(v, list):
        return [fix_int_attr(e) for e in v]
    elif isinstance(v, dict):
        return dict((fix_int_attr(k), fix_int_attr(e)) for (k, e) in list(v.items()))
    else:
        return v

# edit checkpoints to make sure they can be loaded if a configuration already
# exists
def multi_checkpoint_domains(objs):
    # first, check whether we should act at all
    current_domains = list(SIM_object_iterator_for_class("sync_domain"))
    if not current_domains:
        # no need to perform any merge
        return ([], [], [])

    # find out what is the current top domain
    current_remote_domains = list(SIM_object_iterator_for_class(
        "remote_sync_domain"))
    if current_remote_domains:
        if len(current_remote_domains) > 1:
            raise UpdateException("There are several remote domains in "
                                  "the current configuration, which is "
                                  "unsupported.")
        current_top_domains = [x for x in current_domains
                               if x.sync_domain == current_remote_domains[0]]
        if not current_top_domains:
            raise UpdateException("The remote domain seems unconnected to "
                                  "the rest of the domain hierarchy.")
        elif len(current_top_domains) > 1:
            raise UpdateException("There are more than one domain under the "
                                  "remote domain, which is unsupported")
        current_top_domain = current_top_domains[0]
    else:
        current_top_domain = CORE_process_top_domain()

    # find out what is in the checkpoint
    conf_remote_domains = all_objects(objs, 'remote_sync_domain')
    conf_domains = all_objects(objs, 'sync_domain')
    if conf_remote_domains:
        if len(conf_remote_domains) > 1:
            raise UpdateException("More than one remote domain in "
                                  "configuration")
        conf_remote_domain = conf_remote_domains[0]
        if not conf_domains:
            raise UpdateException("Remote domain without sync. domain")
        conf_top_domains = [x for x in conf_domains
                            if x.sync_domain == conf_remote_domain]
        if len(conf_top_domains) > 1:
            raise UpdateException("Multiple domains connected to remote-domain")
        conf_top_domain = conf_top_domains[0]
    elif conf_domains:
        conf_top_domains = [x for x in conf_domains if not x.sync_domain]
        if len(conf_top_domains) > 1:
            raise UpdateException("Multiple top domains")
        conf_remote_domain = None
        conf_top_domain = conf_top_domains[0]
    else:
        # no top-domain found, so merge with current top domain
        conf_remote_domain = None
        conf_top_domain = None

    changed_objects = []
    deleted_objects = []
    if conf_top_domain:
        # check that the latency is matching
        if conf_top_domain.min_latency > current_top_domain.min_latency:
            print ("The loading configuration requires a greater latency than "
                   "currently set. This might cause the configuration loading "
                   "to fail")

        # if there is a remote-domain in the checkpoint, drop it since we won't
        # merge at that level anyway
        if conf_remote_domain:
            deleted_objects.append(conf_remote_domain)
            del objs[conf_remote_domain.name]

        # drop the configuration's top-domain
        deleted_objects.append(conf_top_domain)
        del objs[conf_top_domain.name]

        # redirect all cells and domains depending on it to the current top
        # domain
        cells = all_objects(objs, 'cell')
        for x in cells + conf_domains:
            if x.sync_domain == conf_top_domain:
                changed_objects.append(x)
                x.sync_domain = current_top_domain
    else:
        # there are probably no cells as well, so let the default mechanism
        # handle that
        pass

    return (deleted_objects, changed_objects, [])

def multi_checkpoint_old_links(objs):
    # fix old-style links so they don't have the same name
    def find_link_name(current, used):
        i = 0
        while '%s_%i' % (current, i) in used:
            i += 1
        return '%s_%i' % (current, i)

    changed_objects = []
    allobjs = SIM_object_iterator(None)
    for cls, cls_impl in [('std-ethernet-link', 'ethernet-link'),
                          ('std-generic-link', 'generic-message-link'),
                          ('std-serial-link', 'serial-link')]:
        current_cls_objs = [x for x in allobjs if x.classname == cls]
        current_cls_names = {x.link_name for x in current_cls_objs}

        if current_cls_names:
            conf_cls_objs = all_objects(objs, cls)
            for o in conf_cls_objs:
                if o.link_name in current_cls_names:
                    new_link_name = find_link_name(o.link_name,
                                                   current_cls_names)
                    # change all cell-link objects
                    for l in all_objects(objs, cls_impl):
                        if l.linkname == o.link_name:
                            l.linkname = new_link_name
                            changed_objects.append(l)
                    # change component
                    o.link_name = new_link_name
                    changed_objects.append(o)

    return ([], changed_objects, [])

SIM_register_post_update(multi_checkpoint_domains)

# Find and return the actual file name of an image file, given the
# current checkpoint, simics search path and the checkpoint directory.
# If nothing is found, return None.
def resolve_image_file(fname, checkpoint_path, simics_path, checkpoint_dir):
    m = re.match(r"%(\d+)%/", fname)
    if m:
        index = int(m.group(1))
        if index >= len(checkpoint_path):
            return None
        full_name = os.path.join(checkpoint_path[index], fname[m.end(0):])
        if os.path.exists(full_name):
            return full_name
        return None

    if fname.startswith("%simics%/"):
        return SIM_lookup_file(fname)

    if os.path.isabs(fname):
        if os.path.isfile(fname):
            return fname
        else:
            return None

    for p in [checkpoint_dir] + simics_path:
        if p.startswith("%simics%/"):
            r = SIM_lookup_file(os.path.join(p, fname))
            if r:
                return r
        f = os.path.join(p, fname)
        if os.path.isfile(f):
            return f

    return None

# Upgrade old ps attributes to the new port object clock system
# and remove obsolete attribute "current_global_and_local_time".
def update_clocks_6000(objs):
    changed = set()
    for o in objs.values():
        if hasattr(o, "current_global_and_local_time"):
            remove_attr(o, "current_global_and_local_time")
            changed.add(o)
        if not hasattr(o, "clksrc_state"):
            continue
        o.cell.ps.global_time = o.ps_global_time
        (ticks, _, shift, freq) = o.clksrc_state
        o.vtime.tick = [ticks >> shift,
                        (ticks << (64 - shift)) & 0xffffffffffffffff]
        o.vtime.frequency = freq

        (ps, frac, _, _, _, multiplier) = o.ps_simclk_state
        (_, exp) = math.frexp(multiplier)
        shift = -exp
        o.vtime.ps.cycle = [ps, (frac << (64 - shift)) & 0xffffffffffffffff]
        o.vtime.ps.events = [[ev_obj, ev_class, ev_val, ev_unused, ev_when - ps]
                             for (ev_obj, ev_class, ev_val, ev_unused, ev_when)
                             in o.ps_events]
        remove_attr(o, "clksrc_state")
        remove_attr(o, "ps_global_time")
        remove_attr(o, "ps_hi64")
        remove_attr(o, "ps_events")
        remove_attr(o, "ps_simclk_state")
        remove_attr(o, "simclk_state")
        changed.add(o)
    return ([], list(changed), [])

SIM_register_generic_update(6000, update_clocks_6000)

# Delete reverse execution objects.
def image_remove_rexec_6000(obj):
    obj._unlink()

# Remove image references to the 'rexec' object.
def image_remove_rexec_ref_6000(obj):
    if hasattr(obj, "image_snoop_devices"):
        obj.image_snoop_devices = [d for d in obj.image_snoop_devices
                                   if d.name != "rexec"]

SIM_register_class_update(6000, "image", image_remove_rexec_ref_6000)
SIM_register_class_update(6000, "rev-execution", image_remove_rexec_6000)

# Change "clksrc" attribute to "vtime"
def update_clksrc_attr(obj):
    if hasattr(obj, "clksrc"):
        obj.vtime = obj.clksrc
        del obj.clksrc

SIM_register_class_update(6003, "ps_clock", update_clksrc_attr)
SIM_register_class_update(6003, "cycle_counter", update_clksrc_attr)

renamed_classes = {
    "index_map": "index-map",
    "clock_src": "vtime",
    "ps_clock": "ps-clock",
    "cycle_counter": "cycle-counter",
    "co_execute": "co-execute",
}

for (old, new_cls) in renamed_classes.items():
    def change_name(obj):
        obj.classname = new_cls
    SIM_register_class_update(6003, old, change_name)

# Remove ich10_lan class in favor of v2 - SIMICS-14097
def change_class_ich10_lan(obj):
    obj.classname = "ich10_lan_v2"
    remove_attr(obj, "memory")
    remove_attr(obj, "csr_dummy_4008")
    remove_attr(obj, "csr_dummy_4038")
    remove_attr(obj, "csr_dummy_4124")
    remove_attr(obj, "csr_tx_context0")
    remove_attr(obj, "csr_tx_context1")
    remove_attr(obj, "csr_tx_ctx0_buf")
    remove_attr(obj, "csr_tx_ctx1_buf")
    obj.tx_frame.append(0)
    return ([], [obj.tx_frame], [])

SIM_register_class_update(6033, "ich10_lan", change_class_ich10_lan)

def rename_leader_attribute(obj):
    if not hasattr(obj, "slaver"):
        return
    obj.leader = obj.slaver
    del obj.slaver

SIM_register_class_update(6055, "cell", rename_leader_attribute)

def remove_old_sim_attributes(obj):
    remove_attr(obj, "always_reissue_after_stall")
    remove_attr(obj, "disregard_align")

SIM_register_class_update(7003, "sim", remove_old_sim_attributes)

def remove_cell_list_attribute(obj):
    remove_attr(obj, "cell_list")

SIM_register_class_update(7056, "sim", remove_cell_list_attribute)
