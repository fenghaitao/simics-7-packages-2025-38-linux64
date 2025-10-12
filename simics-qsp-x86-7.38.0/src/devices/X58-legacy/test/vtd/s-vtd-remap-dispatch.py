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


# s-vtd-remap-dispatch.py
# tests the dispatching of DMA requests to remap units

import simics
import conf
import dev_util
import pyobj
import stest

dispatcher = simics.SIM_create_object('x58_remap_dispatcher',
                                      'dispatch_dev', [])

class dummy_device(pyobj.ConfObject):
    """A dummy device with no special behaviour."""
    __class_desc = "dummy device"

class pci_upstream_device(pyobj.ConfObject):
    """A dummy device made to receive pci_upstream requests."""
    __Class_desc = "A dummy device that can receive pci_upstream requests."

    class been_written_to(pyobj.SimpleAttribute(False, 'b')):
        """Set to true when this object receives a pci_upstream request."""

    class pci_upstream(pyobj.Interface):
        def operation(self, gen_transaction, addr_space):
            SIM_log_info(3, self._up.obj, 0,
                         "was accessed through pci_upstream.")
            self._up.been_written_to.val = True
            return Sim_PE_No_Exception

def attribute_test():
    """Tests that the setting and reading of the device list works.

    See hsdes-1805158102 for details on why this is needed."""
    dummy_device_obj = simics.SIM_create_object('dummy_device',
                                                'dummy_dev', [])
    for l in ([], [dummy_device_obj], [dummy_device_obj, dummy_device_obj]):
        dispatcher.gfx_objs = l
        stest.expect_equal(dispatcher.gfx_objs, l)

def dispatching_test():
    """Tests that DMAs from devices are routed according to their membership."""
    default_target = simics.SIM_create_object('pci_upstream_device',
                                              'default_target', [])
    gfx_target = simics.SIM_create_object('pci_upstream_device',
                                          'gfx_target', [])
    dispatcher.default_remapping_unit = default_target
    dispatcher.gfx_remapping_unit = gfx_target
    # What these devices actually do does not matter, we are simply using
    # them as dummy sources for routing
    regular_source = simics.SIM_create_object('dummy_device', 'regular_source',
                                              [])
    gfx_source = simics.SIM_create_object('dummy_device', 'gfx_source', [])
    dispatcher.gfx_objs = [gfx_source]
    for source, target, not_target in (
            (regular_source, default_target, gfx_target),
            (gfx_source, gfx_target, default_target)):
        dispatcher.iface.pci_upstream.operation(
            generic_transaction_t(ini_ptr=source), Sim_Addr_Space_Memory)
        stest.expect_true(target.been_written_to)
        stest.expect_false(not_target.been_written_to)
        # Reset the devices
        target.been_written_to = False
        not_target.been_written_to = False

attribute_test()
dispatching_test()
