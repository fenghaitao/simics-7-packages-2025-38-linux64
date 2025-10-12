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


import cli
from simics import SIM_get_object, SIM_object_iterator, SIM_add_configuration, SIM_delete_objects, SimExc_General, pre_conf_object, SIM_load_module
SIM_load_module('eth-links')
from simmod.eth_links.module_load import (register_pcap_class_commands,
                                          stop_capture)

register_pcap_class_commands('eth-probe')

# info, status
def guess_partner(obj):
    if obj == None:
        return None
    elif is_probe_port(obj):
        return obj.probe
    elif 'endpoint' in obj.classname and hasattr(obj, 'link'):
        return obj.link
    else:
        return obj

def probe_get_info(probe):
    return [ ('Connections',
              [ ('Port A', guess_partner(probe.probe_ports[0].partner)),
                ('Port B', guess_partner(probe.probe_ports[1].partner))]) ]

cli.new_info_command('eth-probe', probe_get_info)

def is_probe(obj):
    return hasattr(obj, 'classname') and obj.classname == 'eth-probe'

def is_probe_port(obj):
    return hasattr(obj, 'classname') and obj.classname == 'eth-probe-port'

# guess, from the device passed as argument, how we should insert the probe on
# the device's side
def guess_dev_obj_attr(obj, port, attr):
    if is_probe(obj):
        obj = obj.probe_ports[1]
    if is_probe_port(obj):
        return [obj, obj, "partner"]

    if not attr:
        if hasattr(obj, 'link'):
            attr = 'link'
        else:
            raise cli.CliError("Device does not have a 'link' attribute, please"
                               " specify the attribute to which the probe"
                               " should be attached")
    else:
        if not hasattr(obj, attr):
            raise cli.CliError("The specified attribute '%s' does not exist in"
                               " object %s. Please specify the attribute that connects the device"
                               " to the link object where the probe should be inserted." %(attr, obj.name))

    if port:
        return [[obj, port], obj, attr]
    else:
        return [obj, obj, attr]

# guess, from the device's "link" attribute, how we should insert the probe on
# the link's side
def guess_link_obj_attr(attr_val):
    if isinstance(attr_val, list):
        obj, port = attr_val
    else:
        obj = attr_val
    if is_probe_port(obj):
        return [obj, obj, 'partner']
    elif hasattr(obj, 'device'):
        return [attr_val, obj, 'device']
    else:
        raise cli.CliError("The probe cannot automatically be inserted between"
                           " the device and the link. Do a manual connection"
                           " instead, using create-unconnected-ethernet-probe")

def object_exists(o):
    try:
        SIM_get_object(o)
        return True
    except SimExc_General:
        return False

# create a new probe
def create_probe(name, clock = None,
                 a_dev = None, a_attr = "",
                 b_dev = None, b_attr = ""):
    # find a proper object name
    if not name or object_exists(name):
        probe_name = cli.get_available_object_name("probe")
    else:
        probe_name = name
    porta_name = "%s_port_a" % probe_name
    portb_name = "%s_port_b" % probe_name

    p = pre_conf_object(probe_name, "eth-probe")
    pa = pre_conf_object(porta_name, "eth-probe-port")
    pb = pre_conf_object(portb_name, "eth-probe-port")
    p.probe_ports = [pa, pb]
    p.queue = clock
    for port in [pa, pb]:
        port.probe = p
        port.queue = clock
        if port == pa:
            port.partner = a_dev
            port.partner_attr = a_attr
            port.side = 0
        else:
            port.partner = b_dev
            port.partner_attr = b_attr
            port.side = 1

    SIM_add_configuration([p, pa, pb], None)

    return (SIM_get_object(probe_name), porta_name, portb_name)

# create and insert a probe to listen to the traffic seen by 'device' on
# 'port', where the network is specified by 'attribute'
def insert_probe(name, device, port, attribute):
    # find out how to modify the connection
    a_dev, a_attr_dev, a_attr = guess_dev_obj_attr(device, port, attribute)
    b_dev, b_attr_dev, b_attr = guess_link_obj_attr(
        getattr(a_attr_dev, a_attr))

    (probe, porta_name, portb_name) = create_probe(
        name, device.queue, a_dev, a_attr, b_dev, b_attr)

    setattr(a_attr_dev, a_attr, SIM_get_object(porta_name))
    setattr(b_attr_dev, b_attr, SIM_get_object(portb_name))

    # if one of the side is another probe, we need to update the partner_attr
    # attribute to point to our own
    if is_probe_port(a_dev):
        a_dev.partner_attr = "partner"
    if is_probe_port(b_dev):
        b_dev.partner_attr = "partner"
    return probe

def insert_probe_cmd(name, deviceinfo, attribute):
    (device, port) = deviceinfo
    probe = insert_probe(name, device, port, attribute)
    return cli.command_return("Created probe '%s'" % probe.name,
                              probe)

def create_probe_cmd(name, clock):
    (probe, porta_name, portb_name) = create_probe(name, clock)
    return cli.command_return("Created unconnected probe '%s'" % probe.name,
                              probe)

def insert_ethernet_probe_expander(string):
    return cli.get_completions(string, [x.name
                                        for x in SIM_object_iterator(None)
                                        if (hasattr(x.iface, 'ethernet_common')
                                            and hasattr(x, 'link')
                                            and x.link != None
                                            and not hasattr(x.iface,
                                                            'link_endpoint'))])

cli.new_command('insert-ethernet-probe', insert_probe_cmd,
                [cli.arg(cli.str_t, 'name', '?', None),
                 cli.arg(cli.obj_t('device', want_port = True), "device",
                         expander = insert_ethernet_probe_expander),
                 cli.arg(cli.str_t, 'attribute', '?', None)], # None -> 'link'
                type = ["Networking", "Probes"],
                short = 'insert Ethernet probe',
                doc = """
Insert an Ethernet probe on the given <arg>device</arg> which must implement
the <iface>ethernet_common</iface> interface.

Optionally the probe may be given a <arg>name</arg>. With <arg>attribute</arg>
you may specify the network to probe; default is the "link" of the given
<arg>device</arg>.""")

cli.new_command('create-unconnected-ethernet-probe', create_probe_cmd,
                [cli.arg(cli.str_t, 'name', '?', None),
                 cli.arg(cli.obj_t('clock', kind = 'cycle'),
                         "clock", '?', None)],
                type = ["Networking", "Probes"],
                short = 'create an unconnected probe',
                doc = """
Create an unconnected Ethernet probe.

Optionally a <arg>name</arg> as well as a <arg>clock</arg> may be given as
arguments.""")

def delete_probe_cmd(probe):
    # let us clean-up the mess
    porta = probe.probe_ports[0]
    portb = probe.probe_ports[1]
    device = porta.partner
    if isinstance(device, list):
        device = device[0]
    link = portb.partner
    if isinstance(link, list):
        link = link[0]
    stop_capture(probe)

    # if one of the side is another probe, update the partner_attr attribute to
    # point to the new partner
    if is_probe_port(device):
        setattr(device, "partner_attr", portb.partner_attr)
    setattr(device, porta.partner_attr, portb.partner)
    if is_probe_port(link):
        setattr(link, "partner_attr", porta.partner_attr)
    setattr(link, portb.partner_attr, porta.partner)
    probe_name = probe.name
    SIM_delete_objects([probe, porta, portb])
    print("Probe '%s' removed and deleted" % probe_name)

cli.new_command('delete', delete_probe_cmd,
                [],
                cls = 'eth-probe',
                type = ["Networking", "Probes"],
                short = 'delete the probe',
                doc = """Delete this eth-probe object.""")
