# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test following I2C operation on AT24Cxx: (bug 18067)
# a START condition immediately followed by a STOP condition.
# Instead of logging error, we could log a message saying this
# behavior is undefined

import pyobj
import stest

# Fake I2C link
class fake_link(pyobj.ConfObject):
    '''Fake I2C link v2 class'''
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class i2c_master_v2(pyobj.Interface):
        def finalize(self):
            pass

        def acknowledge(self, ack):
            self._up.reqs.append(['ack', ack])

i2c_link = pre_conf_object('i2c_link', 'fake_link')

# Create AT24C02A (256B)
i2c_slave = pre_conf_object('i2c_slave', 'AT24Cxx')
slave_address = 0x57
i2c_slave.memory = (
    0x4e, 0x58, 0x49, 0x44, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    5, 0, 0, 0xe0, 12, 2, 0, 0xfd, 0, 0xe0, 12, 2, 1, 0xfd, 0, 0xe0,
    12, 2, 2, 0xfd, 0, 0xe0, 12, 2, 3, 0xfd, 0, 0xe0, 12, 2, 4,
    0xfd,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0x3e, 0xeb, 0xa5, 0x90
    ) + (0,) * (256 - 0x76)
i2c_slave.i2c_address = slave_address
i2c_slave.i2c_link_v2 = i2c_link
SIM_add_configuration([i2c_slave, i2c_link], None)
i2c_slave = conf.i2c_slave
i2c_link = conf.i2c_link

def i2c_start():
    i2c_slave.iface.i2c_slave_v2.start(slave_address << 1)
    stest.expect_equal(i2c_link.object_data.reqs[-1], ['ack', 0])

def i2c_stop():
    i2c_slave.iface.i2c_slave_v2.stop()


i2c_start()
# The test would fail if there is still any error messages printed out
stest.expect_log(i2c_stop, (), i2c_slave, log_type="info")

print("passed: s-bug18067")
