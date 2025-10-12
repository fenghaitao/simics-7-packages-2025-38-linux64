# © 2014 Intel Corporation
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

def get_ep_id_by_node_name(link, node_name):
    for x in link.node_table:
        if x[0] == node_name:
            # Return the endpoint ID
            return x[1]

    # no matching node name
    return -1

def get_node_name_by_ep_id(link, ep_id):
    for x in link.node_table:
        if x[1] == ep_id:
            # Return the node name
            return x[0]

    # no matching endpoint ID
    return None

def set_rssi(dev_obj, node_name, rssi_val):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        link = ep.link
        if link:
            ep_id = get_ep_id_by_node_name(link, node_name)

            if ep_id >= 0:
                ep.iface.ieee_802_15_4_control.set_rssi(ep_id, rssi_val)
            else:
                raise cli.CliError("Cannot find %s." % node_name)

def clear_all_rssi(dev_obj):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        ep.iface.ieee_802_15_4_control.clear_all_rssi()

def rm_rssi(dev_obj, node_name):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        link = ep.link
        if link:
            ep_id = get_ep_id_by_node_name(link, node_name)

            if ep_id >= 0:
                ep.iface.ieee_802_15_4_control.remove_rssi(ep_id)
            else:
                raise cli.CliError("Cannot find %s." % node_name)

def set_rssi_always_drop(dev_obj, rssi_always_drop):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        ep.rssi_always_drop = rssi_always_drop

def set_rssi_random_drop(dev_obj, rssi_random_drop):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        ep.rssi_random_drop = rssi_random_drop

def set_rssi_random_drop_ratio(dev_obj, rssi_random_drop_ratio):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        ep.rssi_random_drop_ratio = rssi_random_drop_ratio

def set_contention_ratio(dev_obj, contention_ratio):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        ep.contention_ratio = contention_ratio

def get_status(dev_obj):
    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    if ep:
        link = ep.link
        if link:
            rssi_table = []
            for e in ep.rssi_table:
                node_name = get_node_name_by_ep_id(link, e[0])
                rssi_val = e[1]
                rssi_table.append((node_name, rssi_val))

            packet_loss_settings = [
                        ("rssi-always-drop", ep.rssi_always_drop),
                        ("rssi-random-drop", ep.rssi_random_drop),
                        ("rssi-random-drop-ratio", ep.rssi_random_drop_ratio)]
            contention_settings = [("contention ratio", ep.contention_ratio)]
    else:
        rssi_table = []
        packet_loss_settings = []
        contention_settings = []

    return [("RSSI Table", rssi_table),
            ("Packet Loss Settings", packet_loss_settings),
            ("Contention Settings", contention_settings)]

def node_name_expander(prefix, dev_obj):
    node_names = []

    ep = dev_obj.ep
    if ep and hasattr(ep, 'ep'):
        # The device is connected to a probe. Further get the endpoint.
        ep = ep.ep

    link = ep.link
    if link:
        node_names = [x[0] for x in link.node_table
                      if len(prefix) == 0 or x[0].find(prefix) != -1]

    return node_names
