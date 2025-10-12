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


# Common functionality for network devices

def get_nic_info(obj):
    info = [("Link", obj.link)]
    if hasattr(obj, 'mac_address'):
        info.append(("MAC address", obj.mac_address))
    if hasattr(obj, 'mac'):
        info.append(("MAC", obj.mac))
    try:
        bw = obj.tx_bandwidth
        if bw == 0:
            bw = "unlimited"
        elif bw % 1000:
            bw = "%d bit/s" % bw
        else:
            bw = bw // 1000
            if bw % 1000:
                bw = "%d kbit/s" % bw
            else:
                bw = "%d Mbit/s" % (bw // 1000)
        info.append(("Transmit limit", bw))
    except:
        pass
    return [(None, info)]

def get_nic_status(obj):
    return []

def get_phy_info(obj):
    info = [("MAC", obj.mac),
            ("Link", obj.link),
            ("PHY Identifier", "%#06x" % obj.phy_id)]
    try:
        bw = obj.tx_bandwidth
        if bw == 0:
            bw = "unlimited"
        elif bw % 1000:
            bw = "%d bit/s" % bw
        else:
            bw = bw // 1000
            if bw % 1000:
                bw = "%d kbit/s" % bw
            else:
                bw = "%d Mbit/s" % (bw // 1000)
        info.append(("Transmit limit", bw))
    except:
        pass
    return [(None, info)]

def get_phy_status(obj):
    link_status = "up" if (obj.mii_regs_status & 0x0004) else "down"
    loopback = "on" if (obj.mii_regs_control & 0x4000) else "off"
    an = "enabled" if (obj.mii_regs_control & 0x1000) else "disabled"
    return [(None,
             [("Link status", link_status),
              ("Loopback mode", loopback),
              ("Auto-negotiation", an)])]

def new_nic_commands(device_name):
    # dummy until not used anymore
    pass
