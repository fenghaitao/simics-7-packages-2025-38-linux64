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


import cli, simics

class_name = 'i2c-link-impl'
ep_class_name = 'i2c-link-endpoint'

def objport(op):
    try:
        obj, port = op
    except (TypeError, ValueError):
        obj, port = (op, None)
    return obj, port

def state(n):
    if not (0 <= n < 13):
        return 'Invalid state'
    return [
        'Idle(idle)',
        'Awaiting start read response from slave(wait_rsp_start_r)',
        'Awaiting start write response form slave(wait_rsp_start_w)',
        'Awaiting read request from master(wait_req_r)',
        'Awaiting write request from master(wait_req_w)',
        'Awaiting read response from slave(wait_rsp_r)',
        'Awaiting write response from slave(wait_rsp_w)',
        'Invalid state',
        'Invalid state',
        'Invalid state',
        'Awaiting stop request from master(wait_stop)',
        'Awaiting start request from remote master(state_wait_remote_master)',
        'Awaiting start response from remote master(state_wait_remote_start_rsp)'][n]

def fmt(op):
    if op == None:
        return 'None'
    obj, port = objport(op)
    if port == None:
        return obj.name
    else:
        return '%s:%s' % (obj.name, port)

def get_slave_iface(obj):
    iface = None
    try:
        if isinstance(obj.device, list):
            o, port = obj.device
            iface = simics.SIM_c_get_port_interface(o, "i2c_slave_v2", port)
        elif obj.device:
            iface = obj.device.iface.i2c_slave_v2
    except AttributeError:
        pass
    return iface

def get_addr_map(obj, ignored_ep = None):
    addr_map = []

    for ep in obj.endpoints:
        if ep == ignored_ep:
            # Prevent infinite loop, one way only
            continue

        if isinstance(ep.device, list) and ep.device[0].classname == "i2c_wire":
            # If i2c_wire was connected, go through it to get the slaves on
            # other links
            for connect_ep in ep.device[0].i2c_link_v2:
                if connect_ep != ep and connect_ep != None:
                    addr_map += get_addr_map(connect_ep.link, connect_ep)
        else:
            iface = get_slave_iface(ep)
            if iface:
                if not iface.addresses:
                    raise Exception(
                        "Device %s does not implement the addresses() method"
                        " in the i2c_slave_v2 interface" % ep.device.name)
                addresses = iface.addresses()
                if not isinstance(addresses, list):
                    raise Exception(
                        "Device %s does not return a list of slave addresses"
                        " in the addresses() method" % ep.device.name)
                addrs = iface.addresses()
                for addr in addrs:
                    if isinstance(addr, int) or addr is None:
                        addr_map.append([addr, ep])
                    else:
                        raise Exception(
                            "Device %s does not return a list of integer values"
                            " in the addresses() method" % ep.device.name)
    return addr_map

def link_info(obj):
    addresses = dict()
    wild_devs = []
    collisions = dict()
    for (addr, ep) in get_addr_map(obj):
        dev_ref = fmt(ep.device)
        if ep.link != obj:
            dev_ref += " (via %s)" % ep.link.name
        if addr is None:
            wild_devs.append(dev_ref)
        elif addr not in addresses:
            addresses[addr] = dev_ref
        else:
            collisions.setdefault(addr, set([addresses[addr]])).add(dev_ref)
    slaves = ([(hex(addr), "ERROR: multiple slaves " + " ".join(devs))
               for addr, devs in sorted(collisions.items())]
              + [(hex(addr), dev)
                 for addr, dev in sorted(addresses.items())])
    if wild_devs:
        slaves.append(("On other addresses", sorted(wild_devs)))
    return [('Latency configuration',
             [('Goal latency', cli.format_seconds(obj.goal_latency)),
              ('Effective latency',
               cli.format_seconds(obj.effective_latency))]),
            ('Connected devices on this link',
             sorted([(ep.name, fmt(ep.device)) for ep in obj.endpoints])),
            ('I2C slave addresses', slaves)]

def link_status(obj):
    if not obj.endpoints:
        return []
    def ep_dev(id):
        for ep in obj.endpoints:
            if ep.id == id:
                return ('%s - %s' % (ep.name, str(fmt(ep.device))))
    return [(None,
             [('Current master', ep_dev(obj.endpoints[0].current_master)),
              ('Current slave', ep_dev(obj.endpoints[0].current_slave))])]

cli.new_info_command(class_name, link_info)
cli.new_status_command(class_name, link_status)

def ep_info(obj):
    disp = [('Link', '%s (%s)' % (obj.link.name, obj.link.classname))]
    disp.append(('Connected device', fmt(obj.device)))

    if get_slave_iface(obj):
        addresses = [hex(x) for x in get_slave_iface(obj).addresses()]
        if addresses:
            disp.append(('I2C addresses listened to', addresses))

    return [(None, disp)]

def ep_status(obj):
    return [(None,
             [('Current state', state(obj.state))])]

cli.new_info_command(ep_class_name, ep_info)
cli.new_status_command(ep_class_name, ep_status)

def wire_info(obj):
    return [(None,
             [('Connected devices', [obj.i2c_link_v2[0], obj.i2c_link_v2[1]])])]

def wire_status(obj):
    return []

cli.new_info_command('i2c_wire', wire_info)
cli.new_status_command('i2c_wire', wire_status)

#
# I2C link components
#
import link_components

class i2c_link_v2(
    link_components.create_simple(link_class = class_name,
                                  endpoint_class = ep_class_name,
                                  connector_type = 'i2c-link',
                                  class_desc =
                                  'new version of an I2C link component',
                                  basename = 'i2c_link_v2',
                                  help_categories = ['I2C Link'])):
    """This component represents a simple i2c link allowing any number
    of devices to connect."""
