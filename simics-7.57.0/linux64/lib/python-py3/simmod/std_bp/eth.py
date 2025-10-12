# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from blueprints import Builder, ConfObject, State, Config, Namespace, blueprint
from blueprints.params import Param
from .state import EthConnectionState, Queue
from . import state

class SwitchConnector(State):
    "Connector used to connect switch ports to the switch."
    switch = ConfObject()
    "The Ethernet switch object (an Ethernet link)."

class SwitchConfig(Config):
    links: list[str] = []

@blueprint([Param("links", "", SwitchConfig, ptype=list)],
            name="ethernet_switch")
def switch(bp: Builder, name: Namespace, config: SwitchConfig, **kwds):
    """Ethernet switch blueprint. Namespaces with 'eth-connector' can be passed
    as arguments, e.g. 'port1 = ns.eth0'."""
    sw = bp.expose_state(name, SwitchConnector)
    sw.switch = bp.obj(name, "eth-switch-link", goal_latency = 0.0001)

    # Add ports to the switch, connected to the specified devices
    for (k, eth) in kwds.items():
        bp.expand(name, k, switch_ep)
        bp.expand(name, f"{k}.cable", cable, eth0=getattr(name, k), eth1=eth)

    # Add ports to the switch, connected to the specified devices
    for (i, link) in enumerate(config.links):
        k = f"port{len(kwds)+i}"
        eth = Namespace(link)
        bp.expand(name, k, switch_ep)
        bp.expand(name, f"{k}.cable", cable, eth0=getattr(name, k), eth1=eth)

class GlobalEndpoints(State):
    all_eps: list[Namespace] = []

def switch_ep(bp: Builder, name: Namespace, sw: SwitchConnector,
              eth: EthConnectionState):
    "Ethernet switch endpoint. I.e. a port in the switch."
    eth.local_attr_name = "device"

    # Assign unique IDs to all endpoints (link requirement?)
    ge = bp.read_state(Namespace("globals"), GlobalEndpoints, private=True)
    ge.all_eps.append(name.ep)
    endpoint_id = (list(ge.all_eps) + [name.ep]).index(name.ep) + 1

    bp.expand(name, "", state.eth, eth=eth,
              connector_class="eth-link-connector")
    eth.local = bp.obj(name.ep, "eth-switch-link-endpoint",
        link = sw.switch,
        device = eth.remote,
        vlan_id = None,
        vlan_trunk = True,
        id = endpoint_id,
    )

def cable(bp: Builder, name: Namespace, *,
          eth0: Namespace, eth1: Namespace|None=None):
    """Ethernet cable which connects two Ethernet devices. The ethernet
    devices are specified as namespace arguments."""
    e0 = bp.read_state(eth0 or name, EthConnectionState, allow_local=True)
    e1 = bp.read_state(eth1 or name, EthConnectionState, allow_local=True)
    e0.remote = e1.local
    e1.remote = e0.local
    e0.remote_connector = e1.local_connector
    e1.remote_connector = e0.local_connector

#
# Service Node
#

def service_node_ftp(bp: Builder, name: Namespace, *, service_node: ConfObject):
    bp.obj(name, "ftp-service",
        server_ip_list = ["10.10.0.1"],
        ftp_helpers = [name.control, name.data],
        tcp = service_node,
    )
    bp.obj(name.control, "ftp-control", ftp = name)
    bp.obj(name.data, "ftp-data", ftp = name)

def service_node_nat(bp: Builder, name, *, service_node: ConfObject):
    bp.obj(name.incoming, "port-forward-incoming-server",
        tcp = service_node,
        udp = service_node,
    )
    bp.obj(name.outgoing, "port-forward-outgoing-server",
        #connections = [["tcp", 0], ["udp", 0]],
        tcp = service_node,
        udp = service_node,
    )

class ServiceNodeConfig(Config):
    enable_real_network = False
    enable_nat = False
    enable_dhcp = False
    enable_real_dns = False
    queue_ns = ""

def snd_finalize(snd, enable_nat, enable_real_dns, enable_dhcp):
    cmd = snd.cli_cmds
    if enable_dhcp:
        cmd.dhcp_add_pool(pool_size = 100, ip = "10.10.0.100")
    if enable_real_dns:
        cmd.enable_real_dns()
    if enable_nat:
        snd.nat.outgoing.connections = [["tcp", 0], ["udp", 0]]

def snd_init(bp: Builder, name: Namespace, *, service_node: ConfObject,
             config: ServiceNodeConfig):
    bp.at_post_instantiate(name, snd_finalize,
        snd=service_node,
        enable_nat=config.enable_nat,
        enable_real_dns=config.enable_real_dns,
        enable_dhcp=config.enable_dhcp)

@blueprint([Param("queue_ns", "Queue object name", ServiceNodeConfig),
            Param("enable_nat", "", ServiceNodeConfig),
            Param("enable_real_dns", "", ServiceNodeConfig),
            Param("enable_dhcp", "", ServiceNodeConfig),
            Param("enable_real_network", "", ServiceNodeConfig)])
def service_node(bp: Builder, name: Namespace, *,
                 queue: Namespace|None = None,
                 config: ServiceNodeConfig, **kwds):
    eth = bp.expose_state(name, EthConnectionState)
    if config.queue_ns:
        qi = bp.read_state(Namespace(config.queue_ns), Queue)
        queue_obj = qi.queue
    else:
        bp.obj(name.cell, "cell")
        bp.obj(name.clock, "clock", freq_mhz=100, cell=name.cell)
        queue_obj = name.clock

    for (k, v) in kwds.items():
        setattr(config, k, v)

    bp.obj(name.init, snd_init,
        service_node = name,
        config = config
    )
    bp.obj(name, "service-node",
        napt_enable = 1,
        recorder = name.recorder,
        queue = queue_obj,
    )
    bp.expand(name, "eth", state.eth, eth = eth)
    eth.local = bp.obj(name.dev, "service-node-device",
        link = eth.remote,
        ip_addresses = ["10.10.0.1/24"],
        service_node = name,
    )
    bp.obj(name.recorder, "recorder")

    bp.expand(name, "ftp", service_node_ftp, service_node = name)
    bp.expand(name, "nat", service_node_nat, service_node = name)
