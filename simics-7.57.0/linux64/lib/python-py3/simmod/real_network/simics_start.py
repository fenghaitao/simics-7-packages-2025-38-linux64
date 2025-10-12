# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from simics import *

import real_ethernet_network as ren
import component_commands
from cli import (
    CliError,
    arg,
    command_return,
    flag_t,
    get_completions,
    new_command,
    str_t,
    )
from simics import (
    SIM_object_parent
)

from comp import pre_obj

def tap_devices():
    return SIM_get_class("rn-eth-bridge-tap").network_devices

def net_adapter_expander(string):
    return get_completions(string, tap_devices())

def tap_available():
    return len(tap_devices()) > 0

#
# ------------ connect-real-network-host --------------
#

# add a route from service-nodes on this network to the real-network router
# unless it already has a default route somewhere else
def get_rn_ip(rn_cmp):
    try:
        return rn_cmp.rn.ip
    except (AttributeError, SimExc_Attribute):
        try:
            return rn_cmp.rn.host_ip
        except (AttributeError, SimExc_Attribute):
            return None

def add_rn_default_route(link_cmp, rn_cmp):
    ip = get_rn_ip(rn_cmp)
    if not ip:
        return
    sn_cmps = ren.ethlinks_connected_instances("service_node_comp", link_cmp)
    for sn_cmp in sn_cmps:
        # enable DNS for the real network
        if not sn_cmp.sn.allow_real_dns:
            print("Enabling DNS lookup on real network.")
            sn_cmp.sn.allow_real_dns = True
        # install a default route
        routes = sn_cmp.sn.routing_table
        for rt in routes:
            if rt[0] == "default":
                break
        else:
            for dev in sn_cmp.sn.eth_interfaces:
                if (hasattr(dev.link, "link")
                    and dev.link.link.component == link_cmp):
                    routes += [["default", "0.0.0.0", ip, dev]]
                    sn_cmp.sn.routing_table = routes
                    print("Adding default route to %s in service-node '%s'" % (
                        ip, sn_cmp))

def del_rn_default_route(link_cmp, rn_cmp):
    ip = get_rn_ip(rn_cmp)
    if not ip:
        return
    sn_cmps = ren.ethlinks_connected_instances("service_node_comp", link_cmp)
    for sn_cmp in sn_cmps:
        routes = sn_cmp.sn.routing_table
        if routes and routes[-1][0] == "default" and routes[-1][2] == ip:
            sn_cmp.sn.routing_table = routes[:-1]
            print("Removing default route to %s from service-node '%s'" % (
                ip, sn_cmp.sn.name))

def delete_cmp_cb(rn_cmp):
    SIM_delete_object(rn_cmp)

def delayed_component_delete(rn_cmp):
    SIM_register_work(delete_cmp_cb, rn_cmp)

def disconnect_rn(rn_cmp, cnt_name, other_cmp):
    rn_cnt = getattr(rn_cmp, cnt_name)
    assert rn_cnt is not None
    for other_cnt in rn_cnt.iface.connector.destination():
        if SIM_object_parent(other_cnt) == other_cmp:
            component_commands.disconnect_connectors_cmd(rn_cnt, other_cnt)
            break

def create_real_network_connection(kind, link_cmp, iface, poll=False):
    ren.check_link_instantiated(link_cmp)
    rns = ren.ethlinks_connected_instances(f"real_network_{kind}_comp",
                                            link_cmp)
    if rns:
        if not any(r.rn.connected for r in rns):
            # Disconnect from switch if underlying real-network disconnected
            for r in rns:
                r.cli_cmds.disconnect_real_network()
        else:
            return None
    if not tap_available():
        raise CliError("No TAP interface found")
    if not iface:
        iface = tap_devices()[0]

    rn_cmp = pre_obj('rn$', 'real_network_%s_comp' % kind, interface = iface)
    rn_cmp = VT_add_objects([rn_cmp])[0]

    component_commands.instantiate_cmd(False, [rn_cmp])
    component_commands.connect_cmd(rn_cmp, "link", link_cmp, None)

    try:
        rn_cmp.rn.connected = True
        if poll:
            rn_cmp.rn.run_in_thread = 2
        print("'%s' connected to the real network." % link_cmp.name)
        if kind == 'host':
            add_rn_default_route(link_cmp, rn_cmp)
    except SimExc_General as ex:
        disconnect_rn(rn_cmp, 'link', link_cmp)
        delayed_component_delete(rn_cmp)
        if kind == 'bridge':
            extra_msg = ""
        else:
            extra_msg = " and assigned an IP address on the simulated network"
        raise CliError("Failed connecting link '%s' to the real network: %s."
                       " Make sure the TAP device '%s' is properly"
                       " configured%s."
                       % (link_cmp.name, ex, iface, extra_msg))
    VT_real_network_warnings()
    return command_return("Created '%s' component '%s'"
                          % (rn_cmp.classname, rn_cmp.name),
                          rn_cmp)

def assert_no_exposed_service_node(link_cmp):
    sn_cmp = ren.find_service_node(link_cmp, None)
    if sn_cmp:
        sn = sn_cmp.sn
        enabled_services = any(sn.services.values())
        if enabled_services:
            raise CliError(
                "The Ethernet link %s about to be bridged to the real network"
                " has a service-node %s with active network services. Such"
                " services may interfere with machines on the real network."
                " Use -f to force a connection anyway."
                % (link_cmp.name, sn_cmp.name))

def real_network_host_cmd(link_cmp, iface, poll):
    return create_real_network_connection('host', link_cmp, iface, poll)

def real_network_bridge_cmd(link_cmp, iface, force, poll):
    if not force:
        assert_no_exposed_service_node(link_cmp)
    return create_real_network_connection('bridge', link_cmp, iface, poll)

####### global connect-real-network commands

def global_real_network_host_cmd(iface, poll):
    link = ren.get_or_create_default_link()
    real_network_host_cmd(link, iface, poll)

def global_real_network_bridge_cmd(iface, force, poll):
    link = ren.get_or_create_default_link()
    real_network_bridge_cmd(link, iface, force, poll)

def rn_disconnect_obj(link_cmp, rn_cmp):
    rn_cmp.rn.connected = False
    if rn_cmp.classname == 'real-network-host':
        del_rn_default_route(link_cmp, rn_cmp)
    disconnect_rn(rn_cmp, 'link', link_cmp)
    delayed_component_delete(rn_cmp)
    print("Disconnecting '%s' from the real network." % link_cmp.name)

def rn_disconnect_cmd(link_cmp):
    ren.check_link_instantiated(link_cmp)
    rn_cmps = ren.ethlinks_connected_instances(
        "real_network_host_comp", link_cmp)
    rn_cmps += ren.ethlinks_connected_instances("real_network_bridge_comp", link_cmp)
    for rn_cmp in rn_cmps:
        rn_disconnect_obj(link_cmp, rn_cmp)

def global_disconnect_cmd():
    link_cmps = ren.ethlinks_find_all_instantiated()
    for l in link_cmps:
        rn_disconnect_cmd(l)
        ren.disconnect_napt_port_forwarding(l)

new_command("connect-real-network-host", global_real_network_host_cmd,
            [arg(str_t, "interface", "?", "",
                 expander = net_adapter_expander),
             arg(flag_t, "-poll")],
            type = ["Networking"],
            short = "connect real host to the simulated network",
            see_also = ['connect-real-network',
                        'connect-real-network-bridge',
                        'disconnect-real-network'],
            doc = """
Connects a TAP interface of the simulation host to a simulated Ethernet link.

The optional <arg>interface</arg> argument specifies the TAP interface of the
host to use.

Use <tt>-poll</tt> to enable poll mode, where the packets are received in full
before handed off to worker threads. This will block all other real time
events while receiving the data, which may impact overall performance. Use at
your own discretion.

This command returns the new real-network component object.
""")

new_command("connect-real-network-bridge", global_real_network_bridge_cmd,
            [arg(str_t, "interface", "?", "",
                 expander = net_adapter_expander),
             arg(flag_t, "-f"),
             arg(flag_t, "-poll")],
            type = ["Networking"],
            short = "connect bridge between real and simulated network",
            see_also = ['connect-real-network',
                        'connect-real-network-host',
                        'disconnect-real-network'],
            doc = """
Creates an Ethernet bridge between a simulated Ethernet link and a real
network through an Ethernet interface of the simulation host.

The optional <arg>interface</arg> argument specifies the TAP interface of the
host to use.

If a service-node with enabled services exists on the Ethernet link
being used, then this command will fail, unless <tt>-f</tt> is
specified.

Use <tt>-poll</tt> to enable poll mode, where the packets are received in full
before handed off to worker threads. This will block all other real time
events while receiving the data, which may impact overall performance. Use at
your own discretion.

This command returns the new real-network component object.
""")

new_command("disconnect-real-network", global_disconnect_cmd,
            type = ["Networking"],
            short = "disconnect from the real network",
            see_also = ['connect-real-network-host',
                        'connect-real-network-bridge'],
            doc = """
Closes all connections to real networks. Also turns off NAPT and
closes all forwarded ports.
""")

#
# real-network commands
#

def register_ethernet_commands(cls):
    new_command("connect-real-network-host", real_network_host_cmd,
                [arg(str_t, "interface", "?", "",
                     expander = net_adapter_expander),
                 arg(flag_t, "-poll")],
                type = ["Networking"],
                cls = cls,
                short = "connect to the real network",
                doc_with = 'connect-real-network-host')

    new_command("connect-real-network-bridge", real_network_bridge_cmd,
                [arg(str_t, "interface", "?", "",
                     expander = net_adapter_expander),
                 arg(flag_t, "-f"),
                 arg(flag_t, "-poll")],
                type = ["Networking"],
                cls = cls,
                short = "connect to the real network",
                doc_with = 'connect-real-network-bridge')

    new_command("disconnect-real-network", rn_disconnect_cmd,
                type = ["Networking"],
                short = "disconnect from the real network",
                cls = cls,
                doc_with = 'disconnect-real-network')
