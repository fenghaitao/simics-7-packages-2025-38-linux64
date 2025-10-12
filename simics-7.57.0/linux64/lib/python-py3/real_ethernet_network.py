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

from cli import (
    CliError,
    assert_not_running,
    get_available_object_name,
    interactive_command,
    obj_t,
    )
from simics import (
    SIM_object_iterator,
    SIM_object_iterator_for_class,
    SIM_object_iterator_for_interface,
    SIM_get_object,
    SIM_load_module,
    SIM_run_command,
    SimExc_General,
    Sim_Connector_Direction_Down,
    )
import component_utils, component_commands

new_ethernet_links = ('eth-hub-link', 'eth-cable-link', 'eth-switch-link')
new_ethernet_link_cmps = ('ethernet_hub', 'ethernet_cable', 'ethernet_switch',
                          'ethernet_vlan_switch')

# for commands working on link components
ethlink_t = obj_t('ethernet link', cls = new_ethernet_link_cmps)

def ethlinks_connected_instances(instance_class, link_cmp):
    # ethernet links only have one object per connector
    return [z.owner for z in
            [y[0] for y in [x.iface.connector.destination()
                            for x in component_utils.get_connectors(link_cmp)]
             if y]
            if hasattr(z, 'owner') and z.owner.classname == instance_class]

# return True if the current configuration contains at least one cycle object
def configuration_contains_a_queue():
    return list(SIM_object_iterator_for_interface(['cycle']))

def check_configuration_contains_a_queue():
    if not configuration_contains_a_queue():
        raise CliError("Command requires a existing cycle queue object.")

def is_multicell_configuration():
    cells = list(SIM_object_iterator_for_class("cell"))
    return len(cells) > 1

def get_first_queue():
    check_configuration_contains_a_queue()
    return list(SIM_object_iterator_for_interface(['cycle']))[0]

def ethlinks_find_all_instantiated():
    return [o for o in SIM_object_iterator(None)
            if o.classname in new_ethernet_link_cmps and o.instantiated]

# create a default ethernet link
def ethlinks_create_default_link():
    SIM_load_module("eth-links")
    name = get_available_object_name("default_eth_switch")
    SIM_run_command("new-ethernet-switch name = %s" % name)
    return SIM_get_object(name)

# connect all empty ethernet link connectors to the given link component
def ethlinks_connect_empty_connectors(link_cmp):
    all_cmps = SIM_object_iterator_for_interface(['component'])
    connected = []
    for c in all_cmps:
        cnts = component_utils.get_connectors(c)
        empty_eth_cnt = [a for a in cnts
                         if (not a.iface.connector.destination()
                             and a.iface.connector.type() == 'ethernet-link'
                             and a.iface.connector.direction()
                             == Sim_Connector_Direction_Down
                             and not (hasattr(a, 'child') and a.child))]
        for e in empty_eth_cnt:
            # ugly quadratic way of finding the empty connector for the link
            link_cnts = component_utils.get_connectors(link_cmp)
            empty_link_cnt = [a for a in link_cnts
                              if (not a.iface.connector.destination())][0]
            component_commands.connect_connectors_cmd(e, empty_link_cnt)
            connected.append((c, e.connector_name))
    return connected

def pr_interactive(s):
    if interactive_command():
        print(s)

def ethlinks_create_and_connect_default_link():
    link_cmp = ethlinks_create_default_link()
    pr_interactive("No ethernet link found, created %s." % link_cmp.name)
    connected = ethlinks_connect_empty_connectors(link_cmp)
    for c, cnt, in connected:
        pr_interactive("Connected %s.%s to %s" % (c.name, cnt,
                                                  link_cmp.name))
    return link_cmp

def get_default_link():
    links = ethlinks_find_all_instantiated()
    if len(links) > 1:
        # we can't choose
        raise CliError("There are more than one Ethernet link. Please "
                       "specify which one the simulated machine is "
                       "connected to.")
    elif links:
        # only one new-style link found, use it
        return links[0]
    else:
        return None

# return a valid default ethernet link or create one if none was found
def get_or_create_default_link():
    link = get_default_link()
    if not link:
        link = ethlinks_create_and_connect_default_link()
    return link

def check_link_instantiated(link):
    if not link.instantiated:
        raise CliError("This command works only with instantiated link "
                       "components")

def get_service_node_impl(obj):
    if obj.classname == 'service_node_comp':
        if obj.instantiated:
            return component_utils.get_component(obj).get_slot('sn')
        else:
            raise CliError('This command only works with an instantiated '
                           'service-node')
    else:
        return obj

# find the first service node connected to 'link'
def find_service_node(link, service_node):
    sns = ethlinks_connected_instances('service_node_comp', link)
    sns.sort(key = lambda x: x.name)
    if not service_node:
        return sns[0] if sns else None
    elif service_node in sns:
        return service_node
    else:
        raise CliError('The service node "%s" is not connected to the'
                       ' link "%s"' % (service_node, link))

default_port = 4000

def get_default_port():
    global default_port
    return default_port

def reset_default_port():
    global default_port
    default_port = 4000

def increase_default_port(inc):
    global default_port
    default_port += inc

def disconnect_napt_port_forwarding(link_cmp):
    assert_not_running()
    sn_cmp = find_service_node(link_cmp, None)
    if sn_cmp:
        sn = sn_cmp.sn
        try:
            pfi = SIM_get_object("%s_port_forward_in" % sn.name)
            # Close opened host ports on host
            pfi.connections = []
        except SimExc_General:
            pass

        try:
            pfo = SIM_get_object("%s_port_forward_out" % sn.name)
            # Close connections from Simics to host
            # Also closes catch-all connections used by NAPT
            pfo.connections = []
        except SimExc_General:
            pass

        sn.napt_enable = 0
        sn.allow_real_dns = False
        reset_default_port()
