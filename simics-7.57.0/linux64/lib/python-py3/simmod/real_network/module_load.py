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


from cli import (
    CliError,
    new_command,
    new_info_command,
    new_status_command,
)
from simics import *

from .simics_start import rn_disconnect_obj

#
# -------------- info --------------
#

def get_info(rn):
    if rn.tap_bridge:
        bridge_info = [("Bridged", True)]
    else:
        bridge_info = [("IP", rn.host_ip), ("Netmask", rn.host_netmask)]
    return [("Host Network",
             [("Connected", "Yes" if rn.connected else "No"),
              ("Interface", rn.interface)]
             + bridge_info)]

new_info_command("rn-eth-bridge-tap", get_info)

#
# -------------- status --------------
#

def get_status(rn):
    return [(None,
             [("Connected", "Yes" if rn.connected else "No")])]

new_status_command("rn-eth-bridge-tap", get_status)

from comp import *
from connectors import EthernetLinkDownConnector

class real_network_common(StandardConnectorComponent):
    '''Common code for read_network_host_comp and real_network_bridge_comp'''
    _do_not_init = object()

    class interface(ConfigAttribute):
        '''Interface to connect to'''
        attrattr = Sim_Attr_Required
        attrtype = 's'
        valid = ['sim_tap0']
        def getter(self):
            return self.val
        def setter(self, val):
            if self._up.instantiated and self._up.obj.configured:
                return Sim_Set_Illegal_Value
            elif self._up.obj.configured:
                self._up.get_slot('rn').interface = val
            self.val = val
            return Sim_Set_Ok

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('link', EthernetLinkDownConnector('rn'))

    def add_objects(self):
        rn = self.add_pre_obj('rn', 'rn-eth-bridge-tap')
        rn.interface = self.interface.val
        rn.connected = True
        self.set_tap_bridge()

    def set_tap_bridge(self):
        pass

class real_network_host_comp(real_network_common):
    '''The "real_network_host_comp" component represents a
       host-based connection to a real network'''
    _class_desc = 'host-based connection to real network'
    _help_categories = ("Networking",)

    class basename(StandardComponent.basename):
        val = 'real_net_host_cmp'

class real_network_bridge_comp(real_network_common):
    '''The "real_network_bridge_comp" component represents a
       bridged connection to a real network'''
    _class_desc = 'bridged connection to real network'
    _help_categories = ("Networking",)

    class basename(StandardComponent.basename):
        val = 'real_net_bridge_cmp'

    def set_tap_bridge(self):
        self.get_slot('rn').tap_bridge = True

#
# -------------- disconnect-real-network --------------
#

def disconnect_rn_cmd(rn_cmp):
    if not rn_cmp.instantiated:
        raise CliError("This command only works with instantiated components")
    link_cmp = rn_cmp.rn.link.link.component
    rn_disconnect_obj(link_cmp, rn_cmp)

for cls in ['real_network_host_comp', 'real_network_bridge_comp']:
    new_command("disconnect-real-network", disconnect_rn_cmd,
                type = ["Networking"],
                cls = cls,
                short = "disconnect from the real network",
                doc = """
                Disconnect the real network connection from a simulated
                Ethernet link.
                """)
