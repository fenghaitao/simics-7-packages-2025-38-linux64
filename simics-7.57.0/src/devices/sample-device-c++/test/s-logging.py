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

stest.expect_log(SIM_create_object, ("sample_device_cxx_logging", "dut", []),
                 log_type="info", regex="Constructing SampleLogging")

def check_signal_log():
    stest.expect_log(conf.dut.iface.signal.signal_raise, [],
                     log_type="info", regex=r"Raising signal \(new level: 1\)")
    stest.expect_log(conf.dut.iface.signal.signal_lower, [],
                     log_type="info", regex=r"Lowering signal \(new level: 0\)")

check_signal_log()
cli.run_command("dut.log-group -disable Signal")
# No log should be emitted now
stest.expect_exception(check_signal_log, [], Exception)
