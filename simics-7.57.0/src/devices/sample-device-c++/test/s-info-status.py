# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import stest
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0
import info_status
import dev_util

# Verify that info/status commands have been registered for all
# classes in this module.
info_status.check_for_info_status(['sample-device-c++'])

all_cls = ["sample_device_cxx_attribute_class_member_variable",
           "sample_device_cxx_attribute_custom_method",
           "sample_device_cxx_attribute_global_method",
           "sample_device_cxx_attribute_pseudo",
           "sample_device_cxx_bank_by_code",
           "sample_device_cxx_bank_by_data",
           "sample_device_cxx_connect",
           "sample_device_cxx_connect_to_descendant",
           "sample_device_cxx_connect_map_target",
           "sample_device_cxx_interface",
           "sample_device_cxx_logging",
           "sample_device_cxx_port_use_confobject",
           "sample_device_cxx_port_use_port",
           "sample_device_cxx_user_interface"]

# sample_device_cxx_attribute_class_member_method requires a value
devs = [SIM_create_object('sample_device_cxx_attribute_class_member_method',
                          'dut_sample_device_cxx_attribute_class_member_method', [["value", 10]])]
# sample_event requires a queue
clk = SIM_create_object('clock', 'clk', [["freq_mhz", 10]])
devs.append(SIM_create_object('sample_device_cxx_event', 'dut_sample_device_cxx_event',
                              [["queue", clk]]))

# Create an instance of each object defined in this module
devs += [SIM_create_object(cls, "dut_" + cls, [])
         for cls in all_cls]

# Run info and status on each object. It is difficult to test whether
# the output is informative, so we just check that the commands
# complete nicely.
for obj in devs:
    for cmd in ['info', 'status']:
        try:
            SIM_run_command(obj.name + '.' + cmd)
        except SimExc_General as e:
            stest.fail(cmd + ' command failed: ' + str(e))
