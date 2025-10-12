# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

#:: pre doc {{

import simics
from comp import PciBusUpConnector, StandardConnectorComponent, SimpleConfigAttribute

class sample_pcie_shim_comp_base(StandardConnectorComponent):
    _do_not_init = object()

    class socket_type(SimpleConfigAttribute("unix-socket", "s", val=['unix-socket', 'tcp'])):
        """socket_type can be either of 'unix-socket' or 'tcp', default is unix-socket"""

    class unix_socket_name(SimpleConfigAttribute(None, "s")):
        """unit_socket_name is the name of the socket"""

    class tcp_port(SimpleConfigAttribute(9842, "i")):
        def setter(self, val):
            if val  < 1024 or val > 65535:
                simics.SIM_attribute_error("tcp_port must be in range [1024, 65535], got %d" % val)
                return simics.Sim_Set_Illegal_Value
            self.val = val

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector("upstream_target", PciBusUpConnector(0, "shim_frontend"))

    def add_objects(self):
        shim = self.add_pre_obj("shim",
                                "sample-pcie-external-connection")

        if self.socket_type.val == "unix-socket":
            self.add_pre_obj(
                    "unix_socket_server",
                    "unix-socket-server",
                    socket_name=self.unix_socket_name.val,
                    client=shim)
        else:
            self.add_pre_obj(
                    "tcp_server",
                    "tcp-server",
                    port=self.tcp_port.val,
                    new_port_if_busy = False,
                    client=shim)

class sample_pcie_switch_shim_comp(sample_pcie_shim_comp_base):
    """Sample PCIe Switch Shim component with external connection"""

    _class_desc = "a sample PCIe Shim Port"
    _help_categories = ()

    def add_objects(self):
        sample_pcie_shim_comp_base.add_objects(self)

        frontend = self.add_pre_obj("shim_frontend", "pcie-port-shim-frontend")

        shim = self.get_slot("shim")
        shim.upstream_target = frontend
        frontend.attr.downstream_shim = shim


class sample_pcie_endpoint_shim_comp(sample_pcie_shim_comp_base):
    """Sample PCIe Endpoint Shim component with external connection"""

    _class_desc = "a sample PCIe Shim Endpoint"
    _help_categories = ()

    def add_objects(self):
        sample_pcie_shim_comp_base.add_objects(self)

        frontend = self.add_pre_obj("shim_frontend", "pcie-endpoint-shim-frontend")

        shim = self.get_slot("shim")
        shim.upstream_target = frontend.port.upstream
        frontend.attr.downstream_shim = shim

# }}
