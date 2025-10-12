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
    Just_Left,
    arg,
    command_return,
    disable_cmd,
    enable_cmd,
    filename_t,
    flag_t,
    get_completions,
    int_t,
    interactive_command,
    new_command,
    new_info_command,
    new_status_command,
    obj_t,
    print_columns,
    str_t,
    )
from simics import *
import nic_common
from socket import inet_aton, inet_ntoa
import table

from ip_address import ip_mask_shorthand, netmask_len, check_ip_addr

from real_ethernet_network import (get_service_node_impl, get_first_queue)
import simmod.ftp_alg.simics_start

from datetime import datetime
from time import ctime

# ethernet link component argument
link_cmp_t = obj_t('ethernet link component',
                   ('ethernet_hub', 'ethernet_cable', 'ethernet_switch', 'ethernet_vlan_switch'))

def get_sn_devs(obj):
    return [x for x in SIM_object_iterator_for_class("service-node-device")
            if x.service_node == obj]

def fmt_lease_time(t):
    if t == 0xffffffff:
        return "infinite"
    else:
        return "%s s" % t

def add_route(obj, net, mask, gw, snd):
    obj.routing_table.append([net, mask, gw, snd])

def get_info(obj):
    snds = get_sn_devs(obj)
    doc = []
    for snd in snds:
        link_or_ep = snd.link
        if link_or_ep and hasattr(link_or_ep.iface, 'ethernet_common'):
            snd_link = "%s (via %s)" % (link_or_ep.link, link_or_ep.name)
        else:
            snd_link = link_or_ep
        doc += [("Interface '%s'" % snd.name,
                 [("Network", snd_link),
                  ("MAC address", snd.mac_address),
                  ("IP addresses", snd.ip_addresses),
                  ("MTU", snd.mtu)])]

    services = obj.services.copy()

    doc += [ ("Services",
              [(svc, "enabled" if en else "disabled")
               for (svc,en) in sorted(services.items())])]
    doc += [ ("DHCP",
              [("Maximum lease time", fmt_lease_time(obj.dhcp_max_lease_time))])]
    doc += [ ("TFTP",
              [("Directory", obj.tftp_root_directory)]) ]
    port_forward_info = []
    for o in SIM_object_iterator_for_class("port-forward-outgoing-server"):
        if o.tcp == obj:
            for out_conn in o.connections:
                if out_conn[1] == 0:
                    listen_port = "All %s output ports" % out_conn[0]
                else:
                    listen_port = "Output %s %s:%d" % (out_conn[0], out_conn[2], out_conn[1])
                if len(out_conn) > 2:
                    forward_port = "Forwarded to %s:%d" % (out_conn[3], out_conn[4])
                else:
                    if obj.napt_enable:
                        forward_port = "Forwarded with NAPT"
                    else:
                        forward_port = "Useless with napt_enable."
                port_forward_info.append((listen_port, forward_port))
    ports = []
    output = {}
    for o in SIM_object_iterator_for_class("port-forward-incoming-server"):
        if o.tcp == obj:
            for in_conn in o.connections:
                ports.append((in_conn[0], in_conn[1], in_conn[2]))
                output[(in_conn[0], in_conn[1], in_conn[2])] = (
                    ("Input %s %s:%d"
                     % (in_conn[0], in_conn[1], in_conn[2]),
                     "Forwarded to %s:%d"
                     % (in_conn[3], in_conn[4])))
            for in_conn in o.temporary_connections:
                ports.append((in_conn[0], in_conn[1]))
                output[(in_conn[0], in_conn[1])] = (("Input %s port %5d" % (in_conn[0], in_conn[1]), "Temporarily forwarded to %s:%d" % (in_conn[2], in_conn[3])))
    ports.sort()
    for p in ports:
        port_forward_info.append(output[p])
    if port_forward_info:
        doc += [ ("Port forwarding", port_forward_info) ]
    return doc

def get_tftp_status(obj):
    return [("TFTP sessions",
             [(f"{client_ip}:{ctid}", f"{method} {filename} ({blocks} blocks)")
              for (_, ctid, method, _, client_ip, filename, blocks)
              in obj.tftp_sessions])]

def get_host_pools_status(obj):
    vals = [[ip, name, domain, psize]
            for (psize, ip, name, domain, _) in obj.host_pools]
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h), (Column_Key_Alignment, "left")]
               for h in ["IP", "Name", "Domain", "Size"]])]
    tbl = table.Table(props, vals)
    txt = tbl.to_string(rows_printed=0, no_row_column=True,
                        border_style="borderless")
    vals = [("", line) for line in txt.splitlines()]
    return [("Host pools", vals)]

def get_status(obj):
    return get_tftp_status(obj) + get_host_pools_status(obj)

new_info_command("service-node", get_info)
new_status_command("service-node", get_status)

### Service Node Component ###

from comp import pre_obj, pre_obj_noprefix
from component_utils import get_component, next_sequence
import component_utils

def have_ftp_server():
    try:
        SIM_get_class("ftp-service")
        return True
    except:
        return False

from comp import *

class service_node_comp(StandardComponent):
    """The "service_node_comp" component represents a network
       service node that can be connected to Ethernet links to
       provide services such as DNS, DHCP/BOOTP, RARP and TFTP.
       A service node component does not have any connectors by
       default. Instead, connectors have to be added using the
       <cmd class="service_node_comp">add-connector</cmd> command."""
    _class_desc = "an Ethernet service node"
    _help_categories = ("Networking",)

    def _initialize(self):
        super()._initialize()
        self.link_info = {}
        self.simics_name_cnt = 0

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    class basename(StandardComponent.basename):
        val = 'service_node_cmp'

    class top_level(StandardComponent.top_level):
        def getter(self):
            return self._up.top.val

    class system_info(StandardComponent.system_info):
        def _initialize(self):
            self.val = "Pseudo Machine for Ethernet-Based Services"

    class system_icon(StandardComponent.system_icon):
        val = "service-node-system.png"

    class component_icon(StandardComponent.component_icon):
        def _initialize(self):
            self.val = "service-node.png"

    class next_connector_id(SimpleAttribute(0, 'i')):
        """Next service-node device ID"""
        pass

    class top(SimpleConfigAttribute(False, 'b', Sim_Attr_Optional)):
        """Create the service-node as a top level component when set to true.
        Default is false."""
        pass

    class dynamic_connectors(Attribute):
        """List of user added connectors"""
        attrtype = "[[iss]|[is]*]"
        valid = []
        def _initialize(self):
            self.val = []
        def getter(self):
            return self.val
        def setter(self, val):
            conn = []
            for v in val:
                if len(v) == 3:
                    id, ip, netmask = v
                    prelen = netmask_len(netmask)
                    conn.append([id, "%s/%d" % (ip, prelen)])
                else:
                    conn.append(v)
            self.val = conn
            for id,ip in self.val:
                # there are no service-node-devices yet when loading a template
                # they will be added in add_objects()
                if self._up.has_slot('snd'):
                    self._up.add_link_connector(id, True)
                else:
                    self._up.add_link_connector(id, False)

    def add_ftp_server(self, ip):
        if not have_ftp_server():
            return
        if self.has_slot('ftp') and self.get_slot('ftp'):
            self.get_slot('ftp').server_ip_list.append(ip)
        else:
            ftp = self.add_pre_obj(None, 'ftp-service',
                                   tcp = self.get_slot('sn'))
            ftp_c = self.add_pre_obj(None, 'ftp-control', ftp = ftp)
            ftp_d = self.add_pre_obj(None, 'ftp-data', ftp = ftp)
            ftp.ftp_helpers = [ftp_c, ftp_d]
            ftp.server_ip_list = [ip]
            [ftp_obj, ftpc_obj, ftpd_obj] = VT_add_objects([ftp, ftp_c, ftp_d])
            self.add_slot("ftp", ftp_obj)
            self.add_slot("ftp_c", ftpc_obj)
            self.add_slot("ftp_d", ftpd_obj)

    def add_link_connector(self, id, has_snd):
        cnt_name = 'connector_link%d' % id
        if not self.has_slot(cnt_name):
            self.add_connector(cnt_name, 'ethernet-link', True, False,
                               False, simics.Sim_Connector_Direction_Down)
        self.link_info[id] = has_snd

    def add_objects(self):
        self.add_slot("snd", [])
        self.add_pre_obj("sn", 'service-node')
        # When the service node is on the top level, use a dedicated clock
        if self.top.val:
            self.add_pre_obj('clock', 'clock', freq_mhz = 100)
        for id,ip in self.dynamic_connectors.val:
            add_obj = True
            for d in self.get_slot('snd'):
                if ip in d.ip_addresses:
                    add_obj = False
            if add_obj:
                # add object if loading component template
                self.add_connector_object(id, ip)
                self.link_info[id] = True

    def add_connector_object(self, id, ip):
        if self.instantiated.val:
            snd = SIM_create_object('service-node-device', '',
                                    [['ip_addresses', [ip]],
                                     ['service_node', self.get_slot('sn')]])
            snd.queue = self.get_slot('sn').queue
        else:
            snd = self.add_pre_obj(None, 'service-node-device')
            snd.ip_addresses = [ip]
            snd.service_node = self.get_slot('sn')
        snd_list = self.get_slot('snd')
        snd_list.append(snd)
        self.component.set_slot_value('snd', snd_list)
        return (snd, 'connector_link%d' % id)

    def add_connector_instance(self, ip):
        id = self.next_connector_id.val
        self.next_connector_id.val += 1
        (snd, cnt_name) = self.add_connector_object(id, ip)
        self.add_link_connector(id, True)
        if self.instantiated.val:
            self.add_snd_info(snd)
        self.dynamic_connectors.val += [[id, ip]]
        return cnt_name

    def add_snd_info(self, snd):
        # add to host list, if not already there
        snd_ip = snd.ip_addresses[0].split("/")[0]
        if len([x for x in self.get_slot('sn').hosts if x[1] == snd_ip]) == 0:
            # the domain name will always be 'network.sim'
            add_host_cmd(self.get_slot('sn'), snd_ip,
                         'simics%d' % self.simics_name_cnt,
                          None, snd.mac_address)
            self.simics_name_cnt += 1
            self.add_ftp_server(snd_ip)

    class component(StandardComponent.component):
        def post_instantiate(self):
            for snd in self._up.get_slot('snd'):
                self._up.add_snd_info(snd)

    class component_connector(Interface):
        def get_link_id(self, cnt):
            slot_name = cnt.connector_name
            return int(slot_name.replace('connector_link', ''))
        def get_check_data(self, cnt):
            link_id = self.get_link_id(cnt)
            return self._up.get_connect_data(link_id)
        def get_connect_data(self, cnt):
            link_id = self.get_link_id(cnt)
            return self._up.get_connect_data(link_id)
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            link_id = self.get_link_id(cnt)
            snd = self._up.get_slot("snd[%d]" % link_id)
            snd.link = attr[0]
        def disconnect(self, cnt):
            link_id = self.get_link_id(cnt)
            self._up.get_slot("snd[%d]" % link_id).link = None

    def get_connect_data(self, link_id):
        if self.link_info[link_id]:
            return [self.get_slot("snd[%d]" % link_id)]
        else:
            return [None]

def get_host_name(node, ip):
    hosts = node.hosts
    for h in hosts:
        if h[1] == ip:
            if len(h[3]) > 0:
                return h[2] + "." + h[3]
            else:
                return h[2]
    return ""

def arp_cmd(obj, del_flag, del_ip):
    obj = get_service_node_impl(obj)
    snds = get_sn_devs(obj)
    if del_flag:
        if del_ip == "":
            raise CliError("No IP address delete specified.")
        found = 0
        for snd in snds:
            arps = snd.neighbors["nc"]
            if len([x for x in arps if x["ip"] == del_ip]):
                found = 1
                snd.neighbors["nc"] = [x for x in arps if x["ip"] != del_ip]
        if not found:
            print("IP address %s not found in ARP table." % del_ip)
        return

    print("Host                     IP               HWaddress            Interface")
    for snd in snds:
        arps = snd.neighbors["nc"]
        for arp in arps:
            print("%-24s" % get_host_name(obj, arp["ip"]), end=' ')
            print("%-16s" % arp["ip"], end=' ')
            print("%-20s" % arp["mac"], end=' ')
            print(snd.name)

for ns in ['service-node', 'service_node_comp']:
    new_command("arp", arp_cmd,
                [arg(flag_t, '-d'),
                 arg(str_t, 'delete-ip', "?", "")],
                type = ["Networking"],
                short = "inspect and manipulate ARP table",
                cls = ns,
                doc = """
Prints the ARP table for the service node if called with no arguments. An ARP
table entry can be deleted by specifying the <tt>-d</tt> flag and the IP
address in <arg>delete-ip</arg>.""")

#
# Routing commands
#

def route_obj_cmd(obj, print_port):
    obj = get_service_node_impl(obj)
    rt = obj.routing_table

    if print_port:
        l = [["Destination", "Netmask", "Gateway", "Port"]]
    else:
        l = [["Destination", "Netmask", "Gateway", "Link"]]

    for r in rt:
        net = r[0]
        mask = r[1]
        gw = r[2]
        port = r[3]
        if net == "default":
            mask = ""
        if gw == "0.0.0.0":
            gw = ""
        if print_port:
            port_name = port.name
        elif port.link:
            if hasattr(port.link.iface, 'ethernet_common'):
                port_name = '%s (via %s)' % (port.link.link.name,
                                             port.link.name)
            else:
                port_name = port.link.name
        else:
            port_name = "<none>"
        l.append([net, mask, gw, port_name])

    print_columns([Just_Left, Just_Left, Just_Left, Just_Left], l)

for ns in ['service-node', 'service_node_comp']:
    new_command("route", route_obj_cmd,
                [arg(flag_t, "-port")],
                type = ["Networking"],
                short = "show the routing table",
                cls = ns,
                doc = """
                Print the routing table.

                By default, the name of the link on which traffic will be send
                is printed in the last column, but if the <tt>-port</tt>
                flag is use, the port device will be printed instead.
                """)

def route_add_obj_cmd(obj, net, mask, gw, link):
    if link.classname == "service-node-device":
        snd = link
    else:
        snds = [ x for x in get_sn_devs(obj) if x.link == link]
        if not snds:
            raise CliError("Cannot add route to network without a connection.")
        snd = snds[0]
    # Do not use 'link' after this point

    if not mask:
        try:
            net, prefix_len = ip_mask_shorthand(net)
        except:
            raise CliError("Malformed network number")
    elif isinstance(mask, str):
        try:
            prefix_len = netmask_len(mask)
        except Exception as e:
            raise CliError("Malformed netmask: %s" % e)
    else:
        prefix_len = mask

    if net == "default":
        if prefix_len:
            raise CliError("Bad netmask for default route")
    elif not prefix_len:
        raise CliError("Missing netmask")

    if gw == "":
        gw = "0.0.0.0"

    add_route(obj, net, prefix_len, gw, snd)

#
# DHCP commands
#

def add_host_cmd(obj, ip, name, domain, mac):
    obj = get_service_node_impl(obj)
    hosts = obj.hosts.copy()

    host = [x for x in hosts if x[1] == ip]
    if len(host):
        hosts.remove(host[0])
        host = host[0]
    else:
        host = None

    n = name.split('.')
    name = n[0]
    d = ".".join(n[1:])
    if d and domain:
        raise CliError("Domain name specified twice.")
    elif d:
        domain = d

    if domain:
        pass
    elif host:
        domain = host[3]
    else:
        domain = 'network.sim'

    if mac:
        pass
    elif host:
        mac = host[0]
    else:
        mac = None

    dups = [x for x in hosts if x[2] == name and x[3] == domain]
    if len(dups):
        raise CliError("Host %s.%s is already in database with IP %s"
                       % (name, domain, dups[0][1]))

    if interactive_command():
        print(("%s host info for IP %s: %s.%s  %s %s"
               % ("Changing" if host else "Adding",
                  ip, name, domain,
                  "MAC:" if mac else "",
                  mac if mac else "")))

    hosts.append([mac, ip, name, domain])
    try:
        obj.hosts = hosts
    except Exception:
        raise CliError("Failed adding host information.")

for ns in ['service-node', 'service_node_comp']:
    new_command("add-host", add_host_cmd,
                [arg(str_t, "ip"),
                 arg(str_t, "name"),
                 arg(str_t, "domain", "?", None),
                 arg(str_t, "mac", "?", None)],
                type = ["Networking"],
                short = "add host entry",
                cls = ns,
                see_also = ['<service-node>.list-host-info'],
                doc = """
                Add or modify a host entry to the DHCP and DNS server tables.
                <arg>ip</arg> is the ip address. <arg>name</arg> may either be
                a host name or a host.domain. The domain can also be set
                in the <arg>domain</arg> argument. If no domain is set, the
                default is network.sim. The <arg>mac</arg> address, if given,
                should be six hexadecimal numbers separated by colon.

                If there already exist an entry with the same address
                as the given ip address, that entry is modified.
                """)

def del_host_cmd(obj, ip, name, domain, mac):
    obj = get_service_node_impl(obj)
    hosts = obj.hosts.copy()

    if name:
        n = name.split('.')
        name = n[0]
        d = ".".join(n[1:])
        if d and domain:
            raise CliError("Domain name specified twice.")
        elif d:
            domain = d

    if not domain:
        domain = 'network.sim'

    hit = [x for x in hosts if ((x[2] == name and x[3] == domain) or x[0] == mac or x[1] == ip)]
    if len(hit):
        hosts.remove(hit[0])
        try:
            obj.hosts = hosts
        except Exception:
            raise CliError("Failed adding host information.")
        return

    raise CliError("Could not find matching host to remove.")

for ns in ['service-node', 'service_node_comp']:
    new_command("delete-host", del_host_cmd,
                [arg(str_t, "ip", "?", None),
                 arg(str_t, "name", "?", None),
                 arg(str_t, "domain", "?", None),
                 arg(str_t, "mac", "?", None)],
                type = ["Networking"],
                short = "delete host entry",
                cls = ns,
                see_also = ['<service-node>.list-host-info'],
                doc = """
                Delete a host entry from the DHCP and DNS server tables.
                Deletes the first entry that matches either name.domain,
                <arg>ip</arg> address, or <arg>mac</arg> address.
                The <arg>name</arg> may specify host name or host.domain.
                The domain may also be set in the <arg>domain</arg> argument.
                if no domain is set, it defaults to network.sim.
                """)


def list_host_info_cmd(obj):
    obj = get_service_node_impl(obj)
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, n)]
               for n in ["IP", "name.domain", "MAC"]])]
    data = []
    for host in obj.hosts:
        data.append([host[1],
                  "%s.%s" % (host[2], host[3]),
                  host[0] if host[0] else ""])
    tbl = table.Table(props, data)
    return command_return(tbl.to_string(rows_printed=0, no_row_column=True) if data else "",
                          obj.hosts)

for ns in ['service-node', 'service_node_comp']:
    new_command("list-host-info", list_host_info_cmd,
                [],
                type = ["Networking"],
                short = "list host info database",
                cls = ns,
                see_also = ['<service-node>.add-host'],
                doc = """
                Print the host information database, used by the DHCP and DNS
                server. If used in an expression the database will be
                returned.
""")

def dhcp_add_pool_cmd(obj, poolsize, ip, name, domain):
    obj = get_service_node_impl(obj)
    pools = list(obj.host_pools)

    if not name:
        name = 'dhcp'

    if not domain:
        domain = 'network.sim'

    pools.append([poolsize, ip, name, domain, []])
    try:
        obj.host_pools = pools
    except SimExc_IllegalValue as msg:
        raise CliError('Failed to add IP address pool entry: %s' % (msg,))

for ns in ['service-node', 'service_node_comp']:
    new_command("dhcp-add-pool", dhcp_add_pool_cmd,
                [arg(int_t, "pool-size"),
                 arg(str_t, "ip"),
                 arg(str_t, "name", "?", None),
                 arg(str_t, "domain", "?", None)],
                type = ["Networking"],
                short = "add DHCP pool",
                cls = ns,
                doc = """
                Add an IP address pool to the DHCP server.  The
                <arg>pool-size</arg> parameter defines the number of
                available addresses in the pool, starting with address
                <arg>ip</arg>. The DNS server will map the addresses to a
                name that is the <arg>name</arg> parameter with a number
                appended, in the <arg>domain</arg> domain.
                """)

def get_ip_address_from_pool_cmd(obj):
    obj = get_service_node_impl(obj)
    pools = list(obj.host_pools)
    for i in range(len(pools)):
        pool = pools[i]
        if pool[0] > 0:
            # Take first IP in pool
            ip = pool[1]
            ip_cmp = ip.split(".")
            ip_vec = list(map(int, ip_cmp))
            ip_vec[3] += 1
            for j in range(3, 0, -1):
                if ip_vec[j] == 255:
                    ip_vec[j] = 0
                    ip_vec[j - 1] += 1
            ip_cmp = list(map(str, ip_vec))
            pool[1] = ".".join(ip_cmp)
            if pool[0] == 1:
                del(pools[i])
            else:
                pool[0] -= 1
                pools[i] = pool
            obj.host_pools = pools
            return ip
    raise CliError('Failed to allocate automatic IP, out of pool entries.')

for ns in ['service-node', 'service_node_comp']:
    new_command("get-ip-address-from-pool", get_ip_address_from_pool_cmd,
                [],
                type = ["Networking"],
                short = "pop an IP address from the DHCP pool",
                cls = ns,
                doc = """
                Pop an IP address from the DHCP pool.
                """)

def lease_obj_cmd(obj):
    obj = get_service_node_impl(obj)
    leases = obj.dhcp_leases
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, n), (Column_Key_Int_Radix, 10)]
               for n in ["IP", "MAC", "Lease (s)", "Left (s)"]])]
    data = []
    for r in leases:
        ip = r[0]
        mac = r[1]
        time = r[3]
        timestamp = r[4]
        if time == 0xffffffff:
            left = "-"
        else:
            age = int(SIM_time(obj)) - timestamp
            left = time - age
        data.append([ip, mac, "infinite" if time == 0xffffffff else time, left])

    tbl = table.Table(props, data)
    print(tbl.to_string(rows_printed=0, no_row_column=True) if data else "")

for ns in ['service-node', 'service_node_comp']:
    new_command("dhcp-leases", lease_obj_cmd,
                [],
                type = ["Networking"],
                short = "print DHCP leases",
                cls = ns,
                doc = """
                Print the list of active DHCP leases.
                """)

#
# DNS commands
#

class RealDNS:
    def __init__(self, obj):
        self.obj = get_service_node_impl(obj)
    def what(self):
        return "Real DNS"
    def is_enabled(self):
        return self.obj.allow_real_dns
    def set_enabled(self, enable):
        self.obj.allow_real_dns = enable

for ns in ['service-node', 'service_node_comp']:
    new_command("enable-real-dns", enable_cmd(RealDNS),
                [],
                type = ["Networking"],
                short = "enable real DNS",
                cls = ns,
                doc = """
                Enable forwarding of DNS queries for unknown hosts to the real
                DNS server.
                """)

for ns in ['service-node', 'service_node_comp']:
    new_command("disable-real-dns", disable_cmd(RealDNS),
                [],
                type = ["Networking"],
                short = "disable real DNS",
                cls = ns,
                doc = """
                Disable forwarding of DNS queries for unknown hosts to the real
                DNS server.
                """)

#
# TFTP commands
#

def tftp_directory(obj, data):
    (t,v,a) = data
    obj = get_service_node_impl(obj)
    if v == 1:
        obj.tftp_root_directory = None
    else:
        obj.tftp_root_directory = v

for ns in ['service-node', 'service_node_comp']:
    new_command("set-tftp-directory", tftp_directory,
                [arg((filename_t(dirs = 1, exist = 1), flag_t),
                     ("dir", "-default"))],
                type = ["Networking", "Files"],
                short = "set TFTP directory",
                cls = ns,
                doc = """
                Set the directory used by the TFTP service for files read and
                written over TFTP. By default or with the <tt>-default</tt>
                flag, the <fun>SIM_lookup_file</fun> is used for finding files
                to read, and the current directory is used for writing files.
                Otherwise the given <arg>dir</arg> will b used.""")

#
# UDP/TCP commands
#

def tcp_info_cmd(obj):
    obj = get_service_node_impl(obj)
    l = [["Protocol", "Service", "Local address", "Foreign Address", "State"]]
    all_pcbs = obj.tcp_pcbs_all
    for r in all_pcbs:
        serv = r[8].name
        if r[10]:
            local = r[1] + ":" + str(r[10])
        else:
            local = r[1] + ":*"
        if r[11]:
            remote = r[2] + ":" + str(r[11])
        else:
            remote = r[2] + ":*"
        state = r[6]
        l.append(["TCP", serv, local, remote, state])
    all_pcbs = obj.udp_pcbs_all
    for r in all_pcbs:
        serv = r[10].name
        if r[7]:
            local = r[1] + ":" + str(r[7])
        else:
            local = r[1] + ":*"
        if r[8]:
            remote = r[2] + ":" + str(r[8])
        else:
            remote = r[2] + ":*"
        l.append(["UDP", serv, local, remote, ""])
    print_columns([Just_Left, Just_Left, Just_Left, Just_Left, Just_Left], l)

for ns in ['service-node', 'service_node_comp']:
    new_command("tcpip-info", tcp_info_cmd,
                [],
                type = ["Networking"],
                short = "show TCP/IP info",
                cls = ns,
                doc = """
                Print all TCP/IP connections.
                """)

#
# service-node-device commands
#

def get_dev_info(obj):
    doc = [(None,
             [("Service node", obj.service_node),
              ("Network", obj.link),
              ("MAC address", obj.mac_address),
              ("IP addresses", obj.ip_addresses)])]
    return doc

def get_dev_status(obj):
    doc = []
    neighbors = obj.neighbors
    nc = [(e["ip"], "%s (%s)" % (e["mac"], e["state"]))
             for e in neighbors["nc"]] or [("-", "empty")]
    doc += [("Neighbor cache", nc)]
    al = [("", "%s%s" % (p[1], ["", "auto"][p[0]]))
          for p in neighbors["al"]] or [("-", "empty")]
    doc += [("Address list", al)]
    pl = [("", "%s" % p)
          for p in neighbors["pl"]] or [("-", "empty")]
    doc += [("Prefix list", pl)]
    rl = [("default" if r[0].endswith("/0") else r[0],
           r[1])
          for r in neighbors["rl"]] or [("-", "empty")]
    doc += [("Router list", rl)]
    return doc

new_info_command("service-node-device", get_dev_info)
new_status_command("service-node-device", get_dev_status)

def en_svc_expander(string, obj):
    obj = get_service_node_impl(obj)
    disabled_services = [x[0] for x in list(obj.services.items()) if not x[1]]
    return get_completions(string, disabled_services)

def dis_svc_expander(string, obj):
    obj = get_service_node_impl(obj)
    enabled_services = [x[0] for x in list(obj.services.items()) if x[1]]
    return get_completions(string, enabled_services)

class NetworkService:
    def __init__(self, obj, name, all):
        self.obj = get_service_node_impl(obj)
        if all:
            self.names = list(self.obj.services.keys())
        elif not name:
            raise CliError("Either use -all or specify a service name")
        else:
            if not name in self.obj.services:
                raise CliError("Unknown network service '%s'" % name)
            self.names = [name]
    def what(self):
        if len(self.names) == 1:
            [name] = self.names
            return "Network service '%s'" % name
        return "All network services"
    def is_enabled(self):
        enabled = [self.obj.services[name] for name in self.names]
        if all(enabled):
            return True
        elif any(enabled):
            return None
        else:
            return False
    def set_enabled(self, enable):
        for name in self.names:
            self.obj.services[name] = enable

for ns in ['service-node', 'service_node_comp']:
    new_command("enable-service", enable_cmd(NetworkService),
                [arg(str_t, 'name', '?', None, expander = en_svc_expander),
                 arg(flag_t, '-all')],
                type = ["Networking"],
                short = "enable network service",
                cls = ns,
                doc = """
Enable the <arg>name</arg> network service in the service-node or all of
them if the <tt>-all</tt> flag is used.
""")

    new_command("disable-service", disable_cmd(NetworkService),
                [arg(str_t, 'name', '?', None, expander = dis_svc_expander),
                 arg(flag_t, '-all')],
                type = ["Networking"],
                short = "disable network service",
                cls = ns,
                doc = """
Disable the <arg>name</arg> network service in the service-node, or all of
them if the <tt>-all</tt> flag is used.""")

#
# port-forward-outgoing-server commands
#

def get_port_fw_out_status(obj):
    raw_conns = obj.active_connections
    if raw_conns:
        conns = []
        for c in raw_conns:
            proto, sim_ip, sim_port, real_ip, real_port = c
            conns.append((proto.upper(),
                          "%s:%d -> %s:%d" % (sim_ip, sim_port,
                                              real_ip, real_port)))
        return [("Active connections", conns)]
    else:
        return []

new_status_command("port-forward-outgoing-server", get_port_fw_out_status)

def add_connector_cmd(obj, ip, netmask):
    ip, prelen = ip_mask_shorthand(ip)
    check_ip_addr(ip)
    if prelen:
        if netmask:
            print("netmask ignored")
    else:
        if netmask:
            try:
                prelen = netmask_len(netmask)
            except Exception as e:
                raise CliError("Malformed netmask: %s" % e)
        else:
            if ':' in ip:
                prelen = 64
            else:
                prelen = 24
    ip = "%s/%d" % (ip, prelen)
    return get_component(obj).add_connector_instance(ip)

new_command('add-connector', add_connector_cmd,
            [arg(str_t, 'ip'),
             arg(str_t, 'netmask', '?', None)],
            short = 'add a service-node connector',
            cls = 'service_node_comp',
            doc = ('Adds a connector to the service-node with specified IP '
                   'address and netmask. A connector must be created for the '
                   'service-node before an Ethernet link can be connected to '
                   'it. The <arg>ip</arg> argument is the IP address that '
                   'the service node will use on the link, and optionally a '
                   'prefix length on the form "1.2.3.4/24". The '
                   '<arg>netmask</arg> argument can be used instead of '
                   'a prefix length for IPv4 addresses for backwards '
                   'compatibility.  The default prefix length for IPv4 '
                   'addresses is 24, and for IPv6 addresses 64.\n\n'
                   'The name of the new connector is returned.'))

from component_commands import connect_cmd

def connect_to_link_cmd(obj, link, ip, netmask, vlan_id):

    cn_name = add_connector_cmd(obj, ip, netmask)

    if "ethernet_vlan_switch" == link.classname:
        try:
            if vlan_id == None:
                raise CliError("No VLAN ID provided")

            cn1 = simics.SIM_get_object(link.cli_cmds.get_free_connector(vlan_id=int(vlan_id)))

            cn2 = simics.SIM_get_object(obj.cli_cmds.get_available_connector(type="ethernet-link"))
            cli.global_cmds.connect(cnt0=cn1, cnt1=cn2)
            print("Connected %s, to VLAN %s, IP %s" % (obj.name, vlan_id, ip))
        except Exception as e:
            raise CliError("Failed to connect service-node to VLAN: %s" % e)

    else:
        connect_cmd(obj, cn_name, link, None)

new_command('connect-to-link', connect_to_link_cmd,
            [arg(link_cmp_t, 'link'),
             arg(str_t, 'ip'),
             arg(str_t, 'netmask', '?', None),
             arg(str_t, 'vlan_id', '?', None)],
            short = 'connect a service-node component to a link',
            cls = 'service_node_comp',
            doc = ("""Connect the service-node to the given <arg>link</arg>.

            The <arg>ip</arg> argument is the IP address that the service
            node will use on the link, and optionally a prefix length on
            the form "1.2.3.4/24". The <arg>netmask</arg> argument can be
            used instead of a prefix length for IPv4 addresses for
            backwards compatibility. The default prefix length for IPv4
            addresses is 24, and for IPv6 addresses 64. Use <arg>vlan_id</arg>
            to connect to VLAN."""))

def change_clock_cmd(obj, new_ref):
    if new_ref.queue:
        obj.sn.queue = new_ref.queue
        for o in obj.snd:
            o.queue = new_ref.queue
    else:
        raise CliError("The object '%s' does not belong to any clock "
                       "so it can not be used as a new reference for "
                       "the service-node" % new_ref.name)

new_command('change-reference-clock', change_clock_cmd,
            [arg(obj_t('reference-object'), 'obj')],
            short = 'change the reference clock of a service-node component',
            cls = 'service_node_comp',
            doc = """
Change the reference clock of a service-node component to <arg>obj</arg>, if
the automatically chosen clock was not optimal for the current configuration.
""")

route_add_doc = """Adds a network, netmask, gateway, remote service
node entry to the service node's routing table. The <arg>net</arg> and
<arg>gateway</arg> are ip addresses in dot notation. The
<arg>netmask</arg> specifies the prefix length either as an ip address
with a number of bits set, or an integer. If the netmask is not set,
it is derived from the <arg>net</arg> argument, which can be in the
form a.b.c.d/pfx. The <arg>link</arg>, is a link component connected
to the remote service node. The default gateway is 0.0.0.0.
"""

def route_add_comp_cmd(c, net, mask, gw, link):
    if not c.instantiated:
        print("This command only works on instantiated components")
        return

    has_link = False
    sn_comp = get_component(c)
    snd_obj = None
    # check that the link has already been connected to the service node
    # component
    for i in range(0, sn_comp.next_connector_id.val):
        cnt_link = sn_comp.get_slot("connector_link%d" % i)
        if not cnt_link.destination:
            continue
        if cnt_link.destination[0].owner == link:
            has_link = True
            if sn_comp.link_info[i]:
                snd_obj = sn_comp.get_slot("snd[%d]" % i)
            break

    if not has_link:
        raise CliError("The service-node is not connected to the link '%s' "
                       "so no route can be set up for it" % link.name)

    route_add_obj_cmd(sn_comp.get_slot('sn'), net, mask, gw, snd_obj)

new_command("route-add", route_add_comp_cmd,
            [arg(str_t, "net"),
             arg(str_t, "netmask", "?", ""),
             arg(str_t, "gateway", "?", ""),
             arg(link_cmp_t, "link")],
            type = ["Networking"],
            short = "add an entry to the routing table",
            cls = "service_node_comp",
            doc = route_add_doc)

for cls in ['service-node', 'service_node_comp']:
    simmod.ftp_alg.simics_start.register_ftp_alg_cmd(cls)
#
# FTP commands
#

def ftp_directory(obj, v):
    if not obj.instantiated:
        raise CliError('This command only works with an instantiated '
                       'service-node')
    elif not hasattr(obj, 'ftp'):
        raise CliError('No FTP service found in the service-node')

    if not v:
        return obj.ftp.ftp_root_directory
    else:
        try:
            obj.ftp.ftp_root_directory = v
        except SimExc_IllegalValue as ex:
            raise CliError(str(ex))

new_command("set-ftp-directory", ftp_directory,
            [arg(filename_t(dirs = 1, exist = 1), "dir", "?")],
            type = ["Networking", "Files"],
            short = "set FTP root directory",
            cls = 'service_node_comp',
            doc = """
            Set the root directory given by <arg>dir</arg> for files read
            and written over FTP. If no argument is given, this command
            will print the current root directory.""")

#
# NTP commands
#
def ntp_set_virtual_time_cmd(obj, date):
    if not obj.instantiated:
        raise CliError('This command only works with an instantiated '
                       'service-node')
    obj = get_service_node_impl(obj)

    def validate_time_str(date_time):
        try:
            return int(datetime.fromisoformat(date).timestamp())

        except ValueError:
            raise CliError("Wrong date format, use "
            "'ISO8601: year-month-dayThour:minute:second'")

    if not hasattr(obj, 'ntp_virtual_base_time'):
        raise CliError('No NTP service found in the service-node')

    if date:
        obj.ntp_virtual_base_time = validate_time_str(date)

def ntp_virtual_time_cmd(obj):
    if not obj.instantiated:
        raise CliError('This command only works with an instantiated '
                       'service-node')
    obj = get_service_node_impl(obj)
    obj.ntp_virtual_time_mode = True

def ntp_time_cmd(obj):
    if not obj.instantiated:
        raise CliError('This command only works with an instantiated '
                       'service-node')
    obj = get_service_node_impl(obj)
    if not hasattr(obj, 'ntp_virtual_base_time'):
        raise CliError('No NTP service found in the service-node')

    return cli.command_return(f"NTP server time: {ctime(obj.ntp_time)}")


new_command("ntp-virtual-time-mode", ntp_virtual_time_cmd,
            type = ["Networking"],
            short = "set virtual time as base time for NTP",
            cls = 'service_node_comp',
            doc = """Set virtual time mode to be used as base time over NTP.
            The current virtual time base will be used.
            To set virtual the time use 'ntp-set-virtual-time.""")

new_command("ntp-set-virtual-time", ntp_set_virtual_time_cmd,
            [arg(str_t, "date", "?", None)],
            type = ["Networking"],
            short = "set time for NTP",
            cls = 'service_node_comp',
            doc = """Set virtual base time to be used over NTP via
            <arg>date</arg>. As default the host time is used.
            If no <arg>date</arg> is given then the host time is used.
            The base is used together with simulated time to be
            transmitted at NTP requests. Given base time must have the
            format ISO8601 as 'yyyy-mm-ddTh:m:s'.""")

new_command("ntp-time", ntp_time_cmd,
            type = ["Networking"],
            short = "get timing mode",
            cls = 'service_node_comp',
            doc = """Get the current NTP time that server sends to
            clients""")
