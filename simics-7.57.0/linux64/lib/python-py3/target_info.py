# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Get a structured description of all the top level components in the system

import itertools
import math
import os
import conf
import simics
import sim_commands
import component_utils

def get_top_components():
    return sorted((x
                   for x in simics.SIM_object_iterator_for_interface(
                           ['component'])
                   if x.top_level and x.instantiated),
                  # place service-node last in the list
                  key = lambda x: ('~' + x.system_info
                                   if 'service_node' in x.classname else
                                   x.system_info))

def get_blueprint_roots(root):
    return sorted(x for x in itertools.chain(
        [root], simics.SIM_object_iterator(root)) if hasattr(x, "blueprint"))

def get_system_info(top):
    return top.system_info or '<machine information missing>'

def get_icon(top):
    return top.machine_icon or top.system_icon or 'empty_machine.png'


def get_comp_hierarchy_recursive(obj, res):
    if not hasattr(obj, 'component'):
        return False
    res.append(obj)
    if obj.component is None:
        return True
    return get_comp_hierarchy_recursive(obj.component, res)

def get_comp_hierarchy(obj):
    res = []
    if not get_comp_hierarchy_recursive(obj.component, res):
        return []
    res.reverse()
    return res

def get_object_top_component(obj):
    comps = get_comp_hierarchy(obj)
    if not comps:
        return None
    return comps[0]

def get_ethernet_connection_counts(top):
    import link_components
    def exclude_eth_link(con):
        # Filter out some unwanted ethernet links.
        comp_hierarchy = get_comp_hierarchy(con)
        if len(comp_hierarchy) < 2:
            return False
        comp = comp_hierarchy[1]
        return (comp.classname == 'std-ethernet-link'
                # when service-node on top level, its connectors should be counted
                or (comp.classname == 'service_node_comp' and not comp.top)
                or isinstance(comp.object_data, link_components.link_component))

    eth_connectors = [con for con
                      in simics.SIM_object_iterator_for_interface(['connector'])
                      if (con.iface.connector.type() == 'ethernet-link'
                          and get_object_top_component(con) == top
                          and not exclude_eth_link(con))]
    # do not count copied connectors twice
    copied = len([con for con in eth_connectors if con.master != con])
    total = len(eth_connectors) - copied
    used = len([con for con in eth_connectors if con.destination])
    return (total, used)

def get_memory_bytes(top):
    mb = 0
    bytes = 0
    comps = (top.components if hasattr(top, "components")
             else get_blueprint_roots(top))
    for c in comps:
        if hasattr(c, 'memory_megs'):
            mb += c.memory_megs
        elif hasattr(c, 'memory_bytes'):
            bytes += c.memory_bytes
    bytes += mb << 20
    if bytes == 0:
        for o in simics.SIM_object_iterator(top):
            if o.classname in {'ram', 'rom'} and hasattr(o.iface, 'ram'):
                bytes += o.iface.ram.size()
    return bytes

# the '-disk' and size attribute test is only there for backward compatibility,
# as this "feature" has been documented at some point. Modern systems should
# implement the disk_component interface
def get_disks(top):
    comps = (top.components if hasattr(top, "components")
             else get_blueprint_roots(top))
    return [c for c in comps
            if (hasattr(c.iface, 'disk_component')
                or (c.classname.endswith('-disk') and hasattr(c, 'size')))]

def get_disk_size(c):
    return (c.iface.disk_component.size()
            if hasattr(c.iface, 'disk_component')
            else c.size)

target_info_changed_hap = None
def _hap_callback(*args):
    simics.SIM_hap_occurred_always(target_info_changed_hap, None, 0, [])

def ensure_target_info_changed_hap():
    global target_info_changed_hap
    if not target_info_changed_hap:
        target_info_changed_hap = simics.SIM_hap_add_type(
            'Target_Info_Changed',
            '',
            None,
            None,
            'Triggered when the information about the target machines '
            + 'changes', 0)
        simics.SIM_hap_add_callback("Component_Hierarchy_Change",
                                    _hap_callback, None)

def disable_target_info_changed_hap():
    simics.SIM_hap_delete_callback("Component_Hierarchy_Change",
                                   _hap_callback, None)

def clean_target_info(info):
    # by fixing SIMICS-15915, class_desc was rephrased, this will take
    # care of those changes
    if info:
        for x in ["models a ", "models an ", "model of ",
                  "provides a ", "provides an "]:
            info = info.replace(x, "")
    return info

class TargetInfoExtractor:
    def __init__(self, look_for_images = False):
        self.look_for_images = look_for_images

    def get_class_desc(self, comp):
        desc = simics.SIM_get_class(comp.classname).class_desc
        desc = desc if desc else "<information missing>"
        desc = clean_target_info(desc)
        return ['System', desc, desc]

    def get_cpu_desc(self, cpus):
        cpu_mhz = set()
        cpu_types = set()
        cpu_count = len(cpus)
        for cpu in cpus:
            try:
                _ = cpu.iface.processor_info
            except (simics.SimExc_Lookup, AttributeError):
                # ignore clocks
                cpu_count -= 1
                continue
            try:
                cpu_mhz.add(str(cpu.iface.cycle.get_frequency() / 1000000))
            except (simics.SimExc_Lookup, AttributeError):
                cpu_mhz.add("n/a")
            if hasattr(cpu, 'cpu_description') and cpu.cpu_description != None:
                cpu_types.add(cpu.cpu_description)
            else:
                cpu_types.add(clean_target_info(cpu.class_desc))
        if cpu_count == 0:
            return "No processor"
        elif len(cpu_types) > 1:
            return "%d of different types" % cpu_count
        elif len(cpu_mhz) > 1:
            return ("%(cnt)d %(type)s, various MHz"
                    % {'cnt' : cpu_count, 'type' : cpu_types.pop()})
        else:
            return ("%(cnt)d %(type)s, %(mhz)s MHz"
                    % {'cnt' : cpu_count,
                       'type' : cpu_types.pop(),
                       'mhz' : cpu_mhz.pop()})

    def get_processor_info(self, comp):
        if hasattr(comp, "cpu_list"):
            cpus = comp.cpu_list
        else:
            cpus = [o for o in simics.SIM_object_iterator(comp)
                    if hasattr(o.iface, "processor_info")]
        name = 'Processors' if len(cpus) > 1 else 'Processor'
        return [name, self.get_cpu_desc(cpus),
                [[cpu, self.get_cpu_desc(cpus)] for cpu in cpus]]

    def get_memory_info(self, top):
        mem_bytes = get_memory_bytes(top)
        return ['Memory', sim_commands.abbrev_size(mem_bytes), mem_bytes]

    def get_ethernet_info(self, top):
        total, used = get_ethernet_connection_counts(top)
        value = [['used', used], ['total', total]]
        if total:
            eth_info = ('%(used)d of %(total)d connected' % dict(value))
        else:
            eth_info = 'None'
        return ['Ethernet', eth_info, value]

    def get_storage_info(self, top):
        disks = get_disks(top)
        num_bytes = sum(get_disk_size(d) for d in disks)
        if disks:
            disk_info = ('%d %s (%s)'
                         % (len(disks),
                            'disks' if len(disks) > 1 else 'disk',
                            sim_commands.abbrev_size(num_bytes)))
        else:
            disk_info = 'No disks'
        return ['Storage', disk_info, [
            ['num_disks', len(disks)], ['size', num_bytes]]]
    def get_namespace(self, top):
        return ['Namespace', simics.SIM_object_name(top), top]
    def get_properties(self, comp):
        return [info(comp) for info in [self.get_namespace,
                                        self.get_class_desc,
                                        self.get_processor_info,
                                        self.get_memory_info,
                                        self.get_ethernet_info,
                                        self.get_storage_info]]

    def get_component_info(self, comp):
        look = ((lambda x: find_image(x, image_fallback))
                if self.look_for_images
                else lambda x: x)
        return [get_system_info(comp), look(get_icon(comp)),
                self.get_properties(comp)]

    def get_blueprint_info(self, bp):
        look = ((lambda x: find_image(x, image_fallback))
                if self.look_for_images
                else lambda x: x)
        return [bp.info, look(bp.icon), self.get_properties(bp)]

    def strip_property_value(self, target_info):
        """Return target info where in each property the value was removed."""
        if not target_info:
            return target_info
        return [info[:2] + [[p[:2] for p in info[2]]] for info in target_info]

    def target_info(self):
        """Get at list describing the system, with one element for each top
        level component.

        Each element has the same structure as returned by
        get_component_info or get_blueprint_info.
        """
        data = [self.get_component_info(comp) for comp in get_top_components()]
        data += [self.get_blueprint_info(bp)
                 for bp in get_blueprint_roots(None)]
        return data

# TODO: Move this to the frontend server

def find_image(name, fallback=lambda x: None):
    for p in conf.sim.module_searchpath:
        f = os.path.join(p, 'images', name)
        if os.path.exists(f):
            return f
    return fallback(name)

image_complaints = set()
def image_fallback(name):
    if name not in image_complaints:
        simics.SIM_log_error(conf.sim, 0, "Component image " + name
                             + " not found")
        image_complaints.add(name)
    return find_image('empty_machine.png')
