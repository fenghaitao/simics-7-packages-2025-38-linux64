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

import stest
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0

import dev_util

dut1 = SIM_create_object('sample_device_cxx_attribute_class_member_variable', 'dut1',
                         [])

stest.expect_equal(dut1.flags, [False, False])
dut1.flags[1] = True
stest.expect_equal(dut1.flags, [False, True])
dut1.flags = [True, False]
stest.expect_equal(dut1.flags, [True, False])

dut2 = SIM_create_object('sample_device_cxx_attribute_class_member_method', 'dut2',
                         [["value", 100]])

stest.expect_equal(dut2.value, 100)
dut2.value = 200
stest.expect_equal(dut2.value, 200)
stest.expect_exception(cli.run_command, ["dut2.value = 1000"], Exception)

dut3 = SIM_create_object('sample_device_cxx_attribute_global_method', 'dut3', [])

stest.expect_equal(dut3.name_and_id, ["", 0])
dut3.name_and_id = ["a", 1]
stest.expect_equal(dut3.name_and_id, ["a", 1])

dut4 = SIM_create_object('sample_device_cxx_attribute_custom_method', 'dut4', [])

stest.expect_equal(dut4.blob, (0,) * 1024)
dut4.blob = (1,) * 1024
stest.expect_equal(dut4.blob, (1,) * 1024)

dut5 = SIM_create_object('sample_device_cxx_attribute_pseudo', 'dut5', [])

# Unreadable
stest.expect_exception(cli.run_command, ["dut5->test_trigger"], Exception)
stest.expect_log(cli.run_command, ["dut5->test_trigger = TRUE"],
                 log_type="info", regex="Test triggered")

dut6 = SIM_create_object('sample_device_cxx_attribute_specialized_converter',
                         'dut6', [])

dut6.my_type = [0xc0ffee, "coffee", conf.sim]
stest.expect_equal(dut6.my_type, [0xc0ffee, "coffee", conf.sim])

dut7 = SIM_create_object('sample_device_cxx_attribute_class_attribute',
                         'dut7', [])

cls = SIM_object_class(dut7)
stest.expect_equal(cls.instance_count, 1)

dut8 = SIM_create_object('sample_device_cxx_attribute_class_attribute',
                         'dut8', [])
stest.expect_equal(cls.instance_count, 2)

SIM_delete_object(dut8)
stest.expect_equal(cls.instance_count, 1)

dut9 = SIM_create_object('sample_device_cxx_attribute_nested_stl_container',
                         'dut9')
stest.expect_equal(dut9.id_strs, [])

dut9.id_strs.append([1, ["a", "b"]])
stest.expect_equal(dut9.id_strs, [[1, ["a", "b"]]])
