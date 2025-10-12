# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
import conf
from stest import expect_equal

clock = simics.pre_conf_object('clock', 'clock')
clock.freq_mhz = 10

test_device = simics.pre_conf_object('test_device', 'test_usb_device')

simics.SIM_add_configuration([test_device, clock], None)
simics.SIM_run_command("load-module usb-comp")
simics.SIM_run_command("new-usb-tablet-component name = usb_tablet_comp")

tablet = conf.usb_tablet_comp.usb_tablet
test_device = conf.test_device
test_device.usb_dev = tablet

def set_transfer_data(addr = 0, ep_num = 0, usb_type = 0,
                      bmReq = 0, bReq = 0, wVal = 0, wInd = 0, wLen = 0,
                      usb_dir = 1, size = 0, status = 0):
    test_device.usb_transfer = [addr, ep_num, usb_type,
                               [bmReq, bReq, wVal, wInd, wLen],
                                usb_dir, size, [], status]

def check_transfer_res(dbuf = [], size = 0, status = 1):
    expect_equal(test_device.transfer_dbuffer, dbuf)
    expect_equal(test_device.transfer_size, size)
    expect_equal(test_device.transfer_status, status)

def check_transfer_status(status = 1):
    expect_equal(test_device.transfer_status, status)
