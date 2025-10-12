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

import dev_util
import conf
import stest
import transaction_splitter_common

# Create an instance of the device to test
mem, _, recv = transaction_splitter_common.create_transaction_splitter()
recv = recv.object_data

test_value = 0xdeadbeefbadc0fee

# full single word
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 4,
                   value = test_value & 0xffffffff,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 1)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 4)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffffff)

# partial single word
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 3,
                   value = test_value & 0xffffff,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 1)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 3)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffff)

# 2 full words
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 8,
                   value = test_value,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 2)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 4)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffffff)

stest.expect_equal(recv.received_txns[1].addr, 4)
stest.expect_equal(recv.received_txns[1].size, 4)
stest.expect_equal(recv.received_txns[1].value, (test_value>>32) & 0xffffffff)

# 2 transactions with incomplete trailing word
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 6,
                   value = test_value & 0xffffffffffff,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 2)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 4)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffffff)

stest.expect_equal(recv.received_txns[1].addr, 4)
stest.expect_equal(recv.received_txns[1].size, 2)
stest.expect_equal(recv.received_txns[1].value, (test_value>>32) & 0xffff)

# more than two full words
test_value = (0xdeadbeefbadc0fee << 32) | 0x12345678
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 12,
                   value = test_value,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 3)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 4)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffffff)

stest.expect_equal(recv.received_txns[1].addr, 4)
stest.expect_equal(recv.received_txns[1].size, 4)
stest.expect_equal(recv.received_txns[1].value, (test_value>>32) & 0xffffffff)

stest.expect_equal(recv.received_txns[2].addr, 8)
stest.expect_equal(recv.received_txns[2].size, 4)
stest.expect_equal(recv.received_txns[2].value, (test_value>>64) & 0xffffffff)

# more than two words with trailing last word
test_value = (0xdeadbeefbadc0fee << 32) | 0x12345678
recv.clear_txns()
mem.cli_cmds.write(address = 0x30,
                   size = 9,
                   value = test_value & 0xffffffffffffffffff,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 3)

stest.expect_equal(recv.received_txns[0].addr, 0)
stest.expect_equal(recv.received_txns[0].size, 4)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffffff)

stest.expect_equal(recv.received_txns[1].addr, 4)
stest.expect_equal(recv.received_txns[1].size, 4)
stest.expect_equal(recv.received_txns[1].value, (test_value>>32) & 0xffffffff)

stest.expect_equal(recv.received_txns[2].addr, 8)
stest.expect_equal(recv.received_txns[2].size, 1)
stest.expect_equal(recv.received_txns[2].value, (test_value>>64) & 0xff)

# unaligned multi word with partial last word
test_value = (0xdeadbeefbadc0fee << 32) | 0x12345678
recv.clear_txns()
mem.cli_cmds.write(address = 0x31,
                   size = 9,
                   value = test_value & 0xffffffffffffffffff,
                   _l = True)

stest.expect_equal(len(recv.received_txns), 3)

stest.expect_equal(recv.received_txns[0].addr, 1)
stest.expect_equal(recv.received_txns[0].size, 3)
stest.expect_equal(recv.received_txns[0].value, test_value & 0xffffff)

stest.expect_equal(recv.received_txns[1].addr, 4)
stest.expect_equal(recv.received_txns[1].size, 4)
stest.expect_equal(recv.received_txns[1].value, (test_value>>24) & 0xffffffff)

stest.expect_equal(recv.received_txns[2].addr, 8)
stest.expect_equal(recv.received_txns[2].size, 2)
stest.expect_equal(recv.received_txns[2].value, (test_value>>56) & 0xffff)
