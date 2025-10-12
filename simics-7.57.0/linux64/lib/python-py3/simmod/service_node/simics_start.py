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


from cli import (
    CliError,
    arg,
    assert_not_running,
    command_quiet_return,
    flag_t,
    get_available_object_name,
    get_completions,
    int_t,
    interactive_command,
    new_command,
    obj_t,
    poly_t,
    run_command,
    str_t,
    )
from simics import *
import sys, socket, re
from socket import inet_aton, inet_ntoa
import itertools

import real_ethernet_network as ren
from ip_address import check_ip_addr, netmask_len, ip_address_is_multicast

#
# Printing port forwarding info.
#

def get_napt_forwards():
    forwards = []
    sn_devs = SIM_object_iterator_for_class("service-node-device")
    for sn_dev in sn_devs:
        if (sn_dev.service_node and sn_dev.link
            and sn_dev.service_node.napt_enable):
            forwards.extend((sn_dev.link, dev_ip)
                            for dev_ip in sn_dev.ip_addresses
                            if not ip_address_is_multicast(dev_ip))
    return forwards

def link_or_ep_name(link_or_ep):
    return (None if not link_or_ep
            else (link_or_ep.link.name if hasattr(link_or_ep, "link")
                  else link_or_ep.name))

def print_napt_forwards(forwards):
    forwards.sort()
    for (link, gateway_ip) in forwards:
        print("NAPT enabled with gateway %s on link %s." % (
            gateway_ip, link_or_ep_name(link)))

def get_dns_forwards():
    forwards = []
    sn_devs = SIM_object_iterator_for_class("service-node-device")
    for sn_dev in sn_devs:
        if (sn_dev.service_node and sn_dev.link
            and sn_dev.service_node.allow_real_dns):
            forwards.extend((sn_dev.link, dev_ip)
                            for dev_ip in sn_dev.ip_addresses
                            # it would be more correct to print the IP
                            # addresses SN actually listens to
                            if not ip_address_is_multicast(dev_ip))
    return forwards

def print_dns_forwards(forwards):
    forwards.sort()
    for (link, gateway_ip) in forwards:
        print("Real DNS enabled at %s on link %s." % (
            gateway_ip, link_or_ep_name(link)))

def get_incoming_forwards():
    forwards = []
    pfis = SIM_object_iterator_for_class("port-forward-incoming-server")
    for pfi in pfis:
        for (proto, host_ip, host_port, tgt_ip, tgt_port) in pfi.connections:
            if proto == "tcp":
                protocol = "TCP"
            else:
                protocol = "UDP"
            gw, link = None, None
            forwards.append((protocol, host_ip, host_port, link,
                             tgt_ip, tgt_port, gw))
    return forwards

def target_ip_exists(target_ip):
    existing_forwards = get_incoming_forwards()
    for (protocol, host_ip, host_port,
         link, tgt_ip, tgt_port, gw) in existing_forwards:
        if tgt_ip == target_ip and tgt_port in (21, 22, 23, 80):
            return True
    return False

def print_incoming_forwards(forwards):
    forwards.sort()
    for (proto, host_ip, host_port, link_name, tgt_ip, tgt_port,
         gateway_ip) in forwards:
        if host_ip == "0.0.0.0":
            # printing 0.0.0.0 is not very user friendly
            host_str = "port %d" % host_port
        else:
            host_str = "%s:%d" % (host_ip, host_port)
        print("Host %s %s -> %s:%d" % (proto, host_str, tgt_ip, tgt_port))

def get_outgoing_forwards():
    forwards = []
    pfos = SIM_object_iterator_for_class("port-forward-outgoing-server")
    for pfo in pfos:
        for conn in pfo.connections:
            if len(conn) in (2, 3):
                continue
            (proto, sn_port, sn_ip, tgt_ip, tgt_port) = conn[:5]
            if proto == "tcp":
                protocol = "TCP"
                sn = pfo.tcp
            else:
                protocol = "UDP"
                sn = pfo.udp
            for sn_dev in sn.eth_interfaces:
                dev_ips = set(ip.split("/")[0] for ip in sn_dev.ip_addresses)
                if (sn_dev.link and sn_ip in dev_ips):
                    forwards.append((protocol, sn_dev.link, sn_ip, sn_port)
                                    + tuple(conn[3:]))
    return forwards

def print_outgoing_forwards(forwards):
    forwards.sort()
    for fwd in forwards:
        (proto, link, sn_ip, sn_port, tgt_ip, tgt_port) = fwd[:6]
        print("%s %s port %d on link %s -> host %s:%d" % (
            sn_ip, proto, sn_port, link_or_ep_name(link), tgt_ip, tgt_port))

#
# port-forwarding commands
#

service_list = { "ftp"    : [ 21, "tcp"],
                 "ssh"    : [ 22, "tcp"],
                 "telnet" : [ 23, "tcp"],
                 "tftp"   : [ 69, "udp"],
                 "http"   : [ 80, "tcp"] }

def service_name(port):
    srv = list(service_list.values())
    for i in range(len(srv)):
        if srv[i][0] == port:
            return list(service_list.keys())[i]
    return ""

gl_default_pf_dest = None

def get_default_pf_dest():
    global gl_default_pf_dest
    return gl_default_pf_dest

def set_default_pf_dest(ip):
    global gl_default_pf_dest
    gl_default_pf_dest = ip

def default_pf_target_cmd(ip):
    if ip:
        check_ip_addr(ip)
        set_default_pf_dest(ip)
        if interactive_command():
            print(("Setting '%s' as default port-forwarding target." %
                   get_default_pf_dest()))
    else:
        def_pf_dest = get_default_pf_dest()
        if not def_pf_dest:
            print("No default port-forwarding target set.")
        else:
            print("Default port-forwarding target: '%s'" % def_pf_dest)

new_command("default-port-forward-target", default_pf_target_cmd,
            [arg(str_t, "target-ip", "?", None)],
            type = ["Networking"],
            short = "set default port forwarding target",
            see_also = ['connect-real-network',
                        'connect-real-network-port-in'],
            doc = """
Sets the IP address of a simulated machine that will be used by the
<cmd>connect-real-network</cmd> command if none is given as argument. This is
useful in single machine configurations where the same IP address,
<arg>target-ip</arg>, is used all the time.
""")

def create_outgoing_port_forward(sn):
    try:
        pfo = SIM_get_object("%s_port_forward_out" % sn.name)
    except SimExc_General:
        attrs = [["tcp", sn], ["udp", sn]]
        pfo = SIM_create_object("port-forward-outgoing-server",
                                "%s_port_forward_out" % sn.name,
                                attrs)
    return pfo

def setup_outgoing_port_forward(sn):
    pfo = create_outgoing_port_forward(sn)
    try:
        old_connections = list(pfo.connections)
        new_connections = old_connections + [["tcp", 0], ["udp", 0]]
        pfo.connections = new_connections
    except SimExc_General as msg:
        print("Failed to setup outgoing port-forward service: %s" % msg)
    return pfo

def create_incoming_port_forward(sn):
    try:
        pfi = SIM_get_object("%s_port_forward_in" % sn.name)
    except SimExc_General:
        pfi = SIM_create_object("port-forward-incoming-server",
                                "%s_port_forward_in" % sn.name,
                                [["tcp", sn],
                                 ["udp", sn]])
    return pfi

def setup_incoming_port_forward(sn, pfo):
    create_incoming_port_forward(sn)

def setup_outgoing_connection(sn, sn_ip, protocol, sn_port, tgt_ip, tgt_port,
                              source_port):
    forwards_before = get_outgoing_forwards()

    pfo = create_outgoing_port_forward(sn)
    # TODO: should check if the port is used for other things too
    old_connections = list(pfo.connections)
    for conn in old_connections:
        if len(conn) in (2, 3):
            continue
        (conn_proto, conn_sn_port,
         conn_sn_ip, conn_tgt_ip, conn_tgt_port) = conn[:5]
        if (conn_sn_ip == sn_ip
            and conn_sn_port == sn_port
            and conn_proto == protocol):
            raise CliError("%s %s:%d of service-node %s already forwarded"
                           " to host %s:%d."
                           % ("TCP" if conn_proto == "tcp" else "UDP",
                              conn_sn_ip, sn_port, sn.name, conn_tgt_ip,
                              conn_tgt_port))
    new_conn = [protocol, sn_port, sn_ip, tgt_ip, tgt_port]
    if source_port:
        new_conn.append(source_port)
    pfo.connections = old_connections + [new_conn]

    forwards_after = get_outgoing_forwards()
    new_forwards = [x for x in forwards_after if not (x in forwards_before)]
    if new_forwards:
        print_outgoing_forwards(new_forwards)
    else:
        raise CliError("Port forwarding setup failed.")

def setup_incoming_connection(sn, protocol, ext_ip, ext_port, int_ip, int_port,
                              strict_host_port, preserve_src):
    forwards_before = get_incoming_forwards()

    if not ext_ip:
        ext_ip = "0.0.0.0"

    pfi = create_incoming_port_forward(sn)

    while True:
        try:
            connection_info = [protocol, ext_ip, ext_port, int_ip, int_port]
            pfi.add_connection = connection_info
            pfi.preserve_ip = preserve_src
            break
        except SimExc_IllegalValue as e:
            if strict_host_port:
                raise CliError("Port forwarding setup failed: %s" % e)
            else:
                ext_port += 1
                if ext_port > 65535:
                    raise CliError("Port forwarding setup failed: %s" % e)

    forwards_after = get_incoming_forwards()
    new_forwards = [x for x in forwards_after if not (x in forwards_before)]
    if new_forwards:
        print_incoming_forwards(new_forwards)
    else:
        raise CliError("Port forwarding setup failed.")

def service_expander(string):
    return get_completions(string, list(service_list.keys()))

def parse_port_service_poly(poly):
    proto = None
    if poly[0] == str_t:
        try:
            port = service_list[poly[1]][0]
            proto = service_list[poly[1]][1]
        except Exception as msg:
            raise CliError("Unknown service %s, use the port number "
                           "instead (%s)." % (poly[1], msg))
    else:
        port = poly[1]
    return (proto, port)

def connect_real_network_port_in(poly, ext_ip, ext_port, tgt_ip, sn, tcp, udp,
                                 strict_host_port, preserve_src):
    (proto, port) = parse_port_service_poly(poly)

    if tcp and udp:
        proto = None
    elif tcp:
        proto = "tcp"
    elif udp:
        proto = "udp"

    if proto:
        setup_incoming_connection(sn, proto, ext_ip, ext_port, tgt_ip, port,
                                  strict_host_port, preserve_src)
    else:
        setup_incoming_connection(sn, "udp", ext_ip, ext_port, tgt_ip, port,
                                  strict_host_port, preserve_src)
        setup_incoming_connection(sn, "tcp", ext_ip, ext_port, tgt_ip, port,
                                  strict_host_port, preserve_src)

def disconnect_real_network_port_in(poly, host_ip, host_port, tgt_ip,
                                    sn, tcp, udp):
    (proto, port) = parse_port_service_poly(poly)

    if tcp and udp:
        proto = None
    elif tcp:
        proto = "tcp"
    elif udp:
        proto = "udp"

    try:
        pfi = SIM_get_object("%s_port_forward_in" % sn.name)
    except SimExc_General:
        raise CliError("Incoming port forwarding is not configured.")

    def match(value, pattern):
        '''Returns whether value matches pattern.
        A pattern of None matches any value.'''
        return pattern == None or value == pattern

    old_conns = list(pfi.connections)
    new_conns = [x for x in old_conns
                 if not all(map(
                     match, x, [proto, host_ip, host_port, tgt_ip, port]))]

    if len(new_conns) == len(old_conns):
        raise CliError("Could not find port forwarding connection to remove.")
    pfi.connections = new_conns

def connect_real_network_port_out(sn_port, sn_ip, tgt_port, tgt_ip, sn,
                                  tcp, udp, source_port):
    if udp or not tcp:
        setup_outgoing_connection(sn, sn_ip, "udp", sn_port, tgt_ip, tgt_port,
                                  source_port)
    if tcp or not udp:
        setup_outgoing_connection(sn, sn_ip, "tcp", sn_port, tgt_ip, tgt_port,
                                  source_port)

def disconnect_real_network_port_out(sn_port, sn_ip, tgt_port, tgt_ip, sn, tcp, udp):
    proto = None

    if tcp and udp:
        proto = None
    elif tcp:
        proto = "tcp"
    elif udp:
        proto = "udp"

    try:
        pfo = SIM_get_object("%s_port_forward_out" % sn.name)
    except SimExc_General:
        raise CliError("Outgoing port forwarding is not configured.")

    old_conns = list(pfo.connections)
    new_conns = [x for x in old_conns
                 if len(x) == 2
                 or not ((proto == None or proto == x[0])
                         and [sn_port, sn_ip, tgt_ip, tgt_port] == x[1:5])]

    if len(new_conns) == len(old_conns):
        raise CliError("Could not find port forwarding connection to remove.")
    pfo.connections = new_conns

def get_target_ip(tgt_ip, required=True):
    if not tgt_ip:
        def_pf_dest = get_default_pf_dest()
        if not def_pf_dest:
            if required:
                raise CliError(
                    "No target IP given for port forwarding, and no default " +
                    "destination configured.")
            else:
                return None
        tgt_ip = def_pf_dest
    check_ip_addr(tgt_ip)
    return tgt_ip

def is_service_node_ip(service_node, ip):
    for dev in service_node.sn.eth_interfaces:
        for dev_ip in dev.ip_addresses:
            if ip == dev_ip.split('/')[0]:
                return True
    return False

def get_service_node_ip_on_link(service_node, link, peer_ip):
    """Get an IP address of the same type as peer_ip that the service node
    has on ethernet_link.  Exclude link-local addresses."""
    v6 = (":" in peer_ip)
    for dev in service_node.sn.eth_interfaces:
        # make sure to ignore sn-devs that are connected to old links
        if hasattr(dev.link, "link") and dev.link.link.component == link:
            for dev_ip in dev.ip_addresses:
                ip, pre = dev_ip.split("/")
                if ip.startswith("fe80:"):
                    continue
                if v6 and ":" in ip:
                    return ip
                if not v6 and ":" not in ip:
                    return ip
    return None

def get_all_service_node_ips(service_node, link):
    """Get all IP address that the service node has on link,
    as a generator.  Exclude link-local addresses."""
    for dev in service_node.sn.eth_interfaces:
        if hasattr(dev.link, "link") and dev.link.link.component == link:
            for dev_ip in dev.ip_addresses:
                ip, pre = dev_ip.split("/")
                if ip.startswith("fe80:"):
                    continue
                yield ip

# make sure that a service-node is connected to link
def find_or_connect_service_node(link, target_ip, sn_ip):
    sn = ren.find_service_node(link, None)
    if not sn:
        # look for a service-node we could connect to the link
        sns = [x for x in set(SIM_object_iterator_for_class('service_node_comp'))
               if x.instantiated]
        if not sns:
            sn_name = get_available_object_name("default_service_node")
            SIM_load_module("service-node")
            run_command("new-service-node-comp name = %s" % sn_name)
            sn = SIM_get_object(sn_name)
        else:
            sn = sns[0]
        if not sn_ip:
            if target_ip:
                # make the connection, assuming that the x.y.z.1 address is
                # free and the netmask is 255.255.255.0
                sn_ip = inet_ntoa(inet_aton(target_ip)[0:3] + b'\1')
            else:
                sn_ip = "10.10.0.1"
        if not sn.queue:
            raise CliError("No clock is associated with %s" % sn.name)

        SIM_run_command("%s.connect-to-link ip = %s/24 link = %s"
                        % (sn.name, sn_ip, link.name))
        ren.pr_interactive("Connecting '%s' to '%s' as %s"
                           % (sn.name, link.name, sn_ip))
    return sn

def connect_real_network_port_in_cmd(port_or_service, link, service_node,
                                     host_ip, host_port,
                                     target_ip, tcp_flag, udp_flag,
                                     strict_host_port_flag, pf_preserve_src):
    assert_not_running()
    # fill the target IP if empty and make sure it is valid
    target_ip = get_target_ip(target_ip)
    if not link:
        link = ren.get_or_create_default_link()
    ren.check_link_instantiated(link)
    sn = ren.find_service_node(link, service_node)
    if not sn:
        raise CliError("No service node found on link %s" % link.name)

    if is_service_node_ip(sn, target_ip):
        raise CliError("Cannot port forward to the service-node itself")

    if host_port == None:
        connect_real_network_port_in(port_or_service, host_ip, 4000,
                                     target_ip, sn.sn, tcp_flag, udp_flag,
                                     strict_host_port_flag, pf_preserve_src)
    else:
        connect_real_network_port_in(port_or_service, host_ip, host_port,
                                     target_ip, sn.sn, tcp_flag, udp_flag,
                                     strict_host_port_flag, pf_preserve_src)

    VT_real_network_warnings()

def disconnect_real_network_port_in_cmd(port_or_service, link, service_node, host_ip,
                                        host_port, target_ip, tcp_flag,
                                        udp_flag):
    assert_not_running()
    target_ip = get_target_ip(target_ip)
    if not link:
        link = ren.get_default_link()
        if not link:
            raise CliError("No link found to disconnect from")
    ren.check_link_instantiated(link)
    sn = ren.find_service_node(link, service_node)
    if not sn:
        raise CliError("No service node found on link %s" % link.name)
    disconnect_real_network_port_in(port_or_service, host_ip, host_port,
                                    target_ip, sn.sn, tcp_flag, udp_flag)

def connect_real_network_port_out_cmd(sn_port, link, service_node, target_ip,
                                      target_port, tcp_flag, udp_flag,
                                      source_port):
    assert_not_running()
    target_ip = get_target_ip(target_ip)
    if not link:
        link = ren.get_or_create_default_link()
    ren.check_link_instantiated(link)
    sn = ren.find_service_node(link, service_node)
    if not sn:
        raise CliError("No service node found on link %s" % link.name)

    if is_service_node_ip(sn, target_ip):
        raise CliError("Cannot port forward to the service node itself")
    ips = list(get_all_service_node_ips(sn, link))
    if not ips:
        raise CliError("Cannot get service node IP")
    for sn_ip in ips:
        connect_real_network_port_out(sn_port, sn_ip, target_port, target_ip,
                                      sn.sn, tcp_flag, udp_flag, source_port)
    VT_real_network_warnings()

def disconnect_real_network_port_out_cmd(sn_port, link, service_node, target_ip, target_port,
                                         tcp_flag, udp_flag):
    assert_not_running()
    target_ip = get_target_ip(target_ip)
    if not link:
        link = ren.get_default_link()
        if not link:
            raise CliError("No link found to disconnect from")

    ren.check_link_instantiated(link)
    sn = ren.find_service_node(link, service_node)
    if not sn:
        raise CliError("No service node found on link %s" % link.name)
    sn_ip = get_service_node_ip_on_link(sn, link, target_ip)
    if not sn_ip:
        raise CliError("Cannot get service node IP")
    disconnect_real_network_port_out(sn_port, sn_ip, target_port, target_ip,
                                     sn.sn, tcp_flag, udp_flag)

def connect_real_network_napt_cmd(link, service_node):
    if not link:
        link = ren.get_default_link()
    ren.check_link_instantiated(link)
    sn_cmp = ren.find_service_node(link, service_node)
    if not sn_cmp:
        raise CliError("No service node found on link %s" % link.name)

    sn = sn_cmp.sn
    if sn.napt_enable:
        print("NAPT already enabled.")
        return

    forwards_before = get_napt_forwards()

    sn.napt_enable = 1
    pfo = setup_outgoing_port_forward(sn)
    setup_incoming_port_forward(sn, pfo) # Empty in for ALG hooks

    forwards_after = get_napt_forwards()
    new_forwards = [x for x in forwards_after if not (x in forwards_before)]
    if new_forwards:
        print_napt_forwards(new_forwards)
    else:
        raise CliError("Port forwarding setup failed.")

def connect_real_network_cmd(target_ip, link, sn_ip):
    assert_not_running()
    target_ip = get_target_ip(target_ip, required=False)
    if not link:
        link = ren.get_or_create_default_link()
    ren.check_link_instantiated(link)
    sn_cmp = find_or_connect_service_node(link, target_ip, sn_ip)

    if target_ip:
        if is_service_node_ip(sn_cmp, target_ip):
            raise CliError("Cannot port forward to the service node")
        if target_ip_exists(target_ip):
            print("The target-ip %s already in use" % target_ip)
            print_incoming_forwards(get_incoming_forwards())
            return None

    connect_real_network_napt_cmd(link, sn_cmp)
    sn = sn_cmp.sn

    if target_ip:
        # TODO: it would be nice to automatically forward ftp/telnet/http
        # over ipv6 as well. Depends on SIMICS-8835.
        connect_real_network_port_in([str_t, "ftp"],
                                     "0.0.0.0",
                                     ren.get_default_port() + 21, target_ip,
                                     sn, 1, 0, 0, False)
        connect_real_network_port_in([str_t, "ssh"],
                                     "0.0.0.0",
                                     ren.get_default_port() + 22, target_ip,
                                     sn, 1, 0, 0, False)
        connect_real_network_port_in([str_t, "telnet"],
                                     "0.0.0.0",
                                     ren.get_default_port() + 23, target_ip,
                                     sn, 1, 0, 0, False)
        connect_real_network_port_in([str_t, "http"],
                                     "0.0.0.0",
                                     ren.get_default_port() + 80, target_ip,
                                     sn, 1, 0, 0, False)

        ren.increase_default_port(1000)
        VT_real_network_warnings()
    else:
        print("No incoming ports opened.")

    forwards_before = get_dns_forwards()
    sn.allow_real_dns = True
    forwards_after = get_dns_forwards()
    new_forwards = [x for x in forwards_after
                    if not (x in forwards_before)]
    print_dns_forwards(new_forwards)

    from simmod.ftp_alg.simics_start import enable_ftp_alg_cmd
    enable_ftp_alg_cmd(sn, check_enabled = False)

    # return the link we might have created
    return command_quiet_return(link)

service_node_comp_t = obj_t('service_node_comp', 'service_node_comp')
service_node_t = poly_t('service-node', service_node_comp_t)

real_network_port_in_doc_common = """
Enable or disable port forwarding from the host that Simics is running on, to
a simulated machine, specified by <arg>target-ip</arg>. The externally visible
port <arg>host-port</arg> on the host is mapped to the port
<arg>target-port</arg> on the simulated machine. The external port
(<arg>host-port</arg>) can be associated with a certain IP address on the host
by specifying the <arg>host-ip</arg> argument.

For commonly used services the string argument <arg>service</arg> can be used
instead of a port number. If several Ethernet links exists, the one that the
simulated machine is connected to must be specified using
<arg>ethernet-link</arg>.

The service-node that will perform the port forwarding is selected
automatically based on the Ethernet link unless one is specified using the
<arg>service-node</arg> argument.

The flags <tt>-tcp</tt> and <tt>-udp</tt> can be used to specify the
protocol to forward. The default is to forward only the usual protocol
for named services and both tcp and udp for numerically specified
ports.

The <arg>host-port</arg> given is only a hint, and the actual port
used may be a different one. The command output shows the actual port
used, and it can also be determined by inspecting the connections
attribute in the appropriate port forwarding object.
"""

new_command("connect-real-network-port-in",
            connect_real_network_port_in_cmd,
            [arg((int_t, str_t), ("target-port", "service"),
                 expander = (service_expander, None)),
             arg(ren.ethlink_t, "ethernet-link"),
             arg(service_node_t, "service-node", "?", None),
             arg(str_t, "host-ip", "?", None),
             arg(int_t, "host-port", "?", None),
             arg(str_t, "target-ip", "?", ""),
             arg(flag_t, "-tcp", "?", 0),
             arg(flag_t, "-udp", "?", 0),
             arg(flag_t, "-f", "?", 0),
             arg(flag_t, "-preserve-ip", "?", False)],
            type = ["Networking"],
            short = "setup port forwarding to a simulated machine",
            see_also = ['connect-real-network',
                        'connect-real-network-port-out',
                        'connect-real-network-napt',
                        'connect-real-network-host',
                        'connect-real-network-bridge',
                        'disconnect-real-network',
                        'disconnect-real-network-port-in'],
            doc = "%s%s" % (real_network_port_in_doc_common,
"""
The flag <tt>-f</tt> can be used to cause the command to fail if the suggested
host port could not be allocated, without the flag the command will assign the
first available port starting from the specified host port and upwards.

The flag <tt>-preserve-ip</tt> let source ip pass through proxy when
doing portforwarding.
"""))

new_command("disconnect-real-network-port-in",
            disconnect_real_network_port_in_cmd,
            [arg((int_t, str_t), ("target-port", "service"),
                 expander = (service_expander, None)),
             arg(ren.ethlink_t, "ethernet-link"),
             arg(service_node_t, "service-node", "?", None),
             arg(str_t, "host-ip", "?", None),
             arg(int_t, "host-port", "?", None),
             arg(str_t, "target-ip", "?", None),
             arg(flag_t, "-tcp", "?", 0),
             arg(flag_t, "-udp", "?", 0)],
            type = ["Networking"],
            short = "remove port forwarding to a simulated machine",
            doc = real_network_port_in_doc_common)

real_network_port_out_doc_common = """
Enable or disable port forwarding to a machine on the real network.

Traffic targeting port <arg>service-node-port</arg> on the service node
connected to <arg>ethernet-link</arg> will be forwarded to port
<arg>target-port</arg> on <arg>target-ip</arg>.

Both tcp and udp will be forwarded unless one of the <tt>-tcp</tt> or
<tt>-udp</tt> flags are given in which case only that protocol will
be forwarded.

The service-node that will perform the port forwarding is selected
automatically based on the Ethernet link unless one is specified using the
<arg>service-node</arg> argument.
"""

new_command("connect-real-network-port-out",
            connect_real_network_port_out_cmd,
            [arg(int_t, "service-node-port"),
             arg(ren.ethlink_t, "ethernet-link"),
             arg(service_node_t, "service-node", "?", None),
             arg(str_t, "target-ip"),
             arg(int_t, "target-port"),
             arg(flag_t, "-tcp", "?", 0),
             arg(flag_t, "-udp", "?", 0),
             arg(int_t, "source-port", "?", None)],
            type = ["Networking"],
            short = "setup port forwarding to real machine",
            see_also = ['connect-real-network',
                        'connect-real-network-port-in',
                        'connect-real-network-napt',
                        'connect-real-network-host',
                        'connect-real-network-bridge',
                        'disconnect-real-network',
                        'disconnect-real-network-port-out'],
            doc = "%s%s" % (real_network_port_out_doc_common,
"""
<arg>source-port</arg> can be used to specify the source port from which
service node forwards packets to the target. If not specified, a dynamically
allocated port will be used."""))

new_command("disconnect-real-network-port-out",
            disconnect_real_network_port_out_cmd,
            [arg(int_t, "service-node-port"),
             arg(ren.ethlink_t, "ethernet-link"),
             arg(service_node_t, "service-node", "?", None),
             arg(str_t, "target-ip"),
             arg(int_t, "target-port"),
             arg(flag_t, "-tcp", "?", 0),
             arg(flag_t, "-udp", "?", 0)],
            type = ["Networking"],
            short = "remove port forwarding to real machine",
            doc = real_network_port_out_doc_common)

new_command("connect-real-network-napt", connect_real_network_napt_cmd,
            [arg(ren.ethlink_t, "ethernet-link"),
             arg(service_node_t, "service-node", "?", None)],
            type = ["Networking"],
            short = "enable NAPT from simulated network",
            see_also = ['connect-real-network',
                        'connect-real-network-port-in',
                        'connect-real-network-port-out',
                        'connect-real-network-host',
                        'connect-real-network-bridge',
                        'disconnect-real-network'],
            doc = """
Enables machines on the simulated Ethernet network <arg>ethernet-link</arg> to
initiate accesses to real hosts without the need to configure the simulated
machine with a real IP address. NAPT (Network Address Port Translation) uses
the IP address and a port number of the host that Simics is running on to
perform the access. Replies are then translated back to match the request from
the simulated machine. This command also enables NAPT for accesses that are
initiated from the simulated machine.

The service-node that will perform the port forwarding is selected
automatically based on the Ethernet link unless one is specified using the
<arg>service-node</arg> argument.
""")

def register_connect_real_network_napt_cmd(cls, see_also):
    new_command("connect-real-network-napt", connect_real_network_napt_cmd,
                [arg(service_node_t, "service-node", "?", None)],
                type = ["Networking"],
                cls = cls,
                short = "enable NAPT from simulated network",
                see_also = see_also,
                doc_with = 'connect-real-network-napt')


new_command("connect-real-network", connect_real_network_cmd,
            [arg(str_t, "target-ip", "?", ""),
             arg(ren.ethlink_t, "ethernet-link", "?", None),
             arg(str_t, "service-node-ip", "?", "")],
            type = ["Networking"],
            short = "connect a simulated machine to the real network",
            see_also = ['default-port-forward-target',
                        'connect-real-network-napt',
                        'connect-real-network-port-in',
                        'connect-real-network-port-out',
                        'connect-real-network-host',
                        'connect-real-network-bridge',
                        'disconnect-real-network'],
            doc = """
Enables NAPT for accesses that are initiated from the simulated machine.

If <arg>target-ip</arg> is specified, the command also enables port forwarding
from the host that Simics is running on, to a simulated machine
specified by <arg>target-ip</arg>, allowing access from real hosts to
the simulated one.  If <arg>target-ip</arg> is already used for any of
the target ports 21, 22, 23, or 80, this command just prints the
current port forwarding.

Ports are opened on the host for a number of commonly used protocols (such as
FTP and telnet). Additional ports can be configured using the
<cmd>connect-real-network-port-in</cmd> command.

Port forwarding can be enabled for several simulated machines at the same
time.

If several Ethernet links exists, the one that the simulated machine is
connected to must be specified as <arg>ethernet-link</arg>. If no Ethernet link
exists, one will be created and all Ethernet devices are connected to it.

A <class>service-node</class> will also be added to the link if there
isn't one connected already. If a service-node is added it will either
get the IP address <arg>service-node-ip</arg>, if it was specified, or
the IP of the target with the lowest byte set to 1. If neither
<arg>service-node-ip</arg> nor <arg>target-ip</arg> is specified, it
will get the <tt>10.10.0.1</tt> as IP.

If a default port-forwarding target has been set using the
<cmd>default-port-forward-target</cmd> command, this will be used as
default value for the <arg>target-ip</arg> parameters.
""")

def list_pf_setup_cmd():
    napt_forwards = get_napt_forwards()
    dns_forwards = get_dns_forwards()
    incoming_forwards = get_incoming_forwards()
    outgoing_forwards = get_outgoing_forwards()

    print_napt_forwards(napt_forwards)
    if napt_forwards and dns_forwards:
        print()
    print_dns_forwards(dns_forwards)
    if (napt_forwards or dns_forwards) and incoming_forwards:
        print()
    print_incoming_forwards(incoming_forwards)
    if (napt_forwards or dns_forwards or incoming_forwards) and outgoing_forwards:
        print()
    print_outgoing_forwards(outgoing_forwards)

    return command_quiet_return([list(t) for t in incoming_forwards])

new_command("list-port-forwarding-setup", list_pf_setup_cmd,
            [],
            type = ["Networking"],
            short = "view the port forwarding setup",
            see_also = ['connect-real-network',
                        'connect-real-network-napt',
                        'connect-real-network-port-in',
                        'connect-real-network-port-out',],
            doc = """
Lists the current port forwarding and NAPT configuration.
""")

def allocate_next_addr(vec, fmt_str, separator):
    def carry_add_8bit(vec):
        num_elements = len(vec)
        vec[num_elements - 1] += 1
        for i in range(num_elements - 1, 0, -1):
            if vec[i] == 256:
                vec[i] = 0
                vec[i - 1] += 1
    as_str = [fmt_str % x for x in vec]
    carry_add_8bit(vec)
    return separator.join(as_str)

auto_mac_next = [0x0, 0x17, 0xa0, 0x0, 0x0, 0x0]

def get_auto_mac_address_cmd():
    global auto_mac_next
    return allocate_next_addr(auto_mac_next, "%02x", ":")

new_command("get-auto-mac-address", get_auto_mac_address_cmd,
            [],
            type = ["Networking"],
            short = "get an unused MAC address",
            doc = """
            Get an unused MAC address.
            """)

from update_checkpoint import *

def remove_nfs(set):
    nfs = [n for n in list(set.values()) if n.name in ['nfs']]
    for ns in nfs:
        del set[ns.name]
    return ([], [], [])

def remove_nfs_7003(obj):
    if hasattr(obj, 'static_slots'):
        if obj.static_slots['nfs']:
            del obj.static_slots['nfs']


def remove_nfs_server(set):
    nfs = [n for n in list(set.values()) if n.classname in ['nfs_server']]
    for ns in nfs:
        del set[ns.name]
    return (nfs, [], [])

def is_service_node_with_udp_pcbs(obj):
    return obj.classname == 'service-node' and getattr(obj, 'udp_pcbs', None)

def udp_pcbs_contains_nfs_server(entry):
    return (isinstance(entry[-2], pre_conf_object)
            and entry[-2].__class_name__ == 'nfs_server')

def remove_nfs_server_from_udp_pcbs(objects):
    service_nodes = [x for x in list(objects.values()) if (
        is_service_node_with_udp_pcbs(x))]
    changed_objects = set()
    for service_node in service_nodes:
        to_delete = []
        for entry in service_node.udp_pcbs:
            if udp_pcbs_contains_nfs_server(entry):
                to_delete.append(entry)
        if not to_delete:
            continue
        changed_objects.add(service_node)
        for entry in to_delete:
            while entry in service_node.udp_pcbs:
                service_node.udp_pcbs.remove(entry)
    return ([], list(changed_objects), [])

SIM_register_generic_update(7003, remove_nfs_server_from_udp_pcbs)
install_class_configuration_update(7003, 'service_node_comp', remove_nfs_7003)
install_generic_configuration_update(7003, remove_nfs_server)
