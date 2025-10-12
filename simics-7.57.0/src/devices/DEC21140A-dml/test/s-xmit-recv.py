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


# Test transmission and reception of ethernet packets.
# This test is very superficial; it mainly serves to illustrate testing
# concepts.

from common import *
from stest import expect_equal, fail

(eth, test_state) = create_config()
regs = dec_regs(eth)

Csr5 = dev_util.Bitfield_LE({'nis' : 16,
                             'tu'  : 2,
                             'ti'  : 0})

Csr6 = dev_util.Bitfield_LE({'ps' : 18,
                             'st' : 13,
                             'pr' : 6,
                             'sr' : 1})

csr3 = dev_util.Register_LE(eth.bank.csr, 0x18)
csr4 = dev_util.Register_LE(eth.bank.csr, 0x20)
csr5 = dev_util.Register_LE(eth.bank.csr, 0x28, bitfield = Csr5)
csr6 = dev_util.Register_LE(eth.bank.csr, 0x30, bitfield = Csr6)
csr7 = dev_util.Register_LE(eth.bank.csr, 0x38)

# Allow device to act as a PCI bus master, so it can access memory
regs.cfcs.m = 1

# Test frame transmission

# Set up descriptors in memory:
# Make a single descriptor with a single buffer
xmit_desc_addr = 0x81234560
xmit_buf_size = 512
xmit_buf_addr = 0xcafe5000

# Map a Transmit_desc on our test memory at xmit_desc_addr, then initialize it
xmit_desc = dev_util.Layout_LE(test_state.memory, xmit_desc_addr, Transmit_desc)
xmit_desc.tdes0.write(0, own = 1)
xmit_desc.tdes1.write(0, ic = 1, fs = 1, ls = 1, ter = 1, tbs1 = xmit_buf_size)
xmit_desc.buf_addr1 = xmit_buf_addr
xmit_desc.buf_addr2 = 0xa5a5a5a5

# Make a buffer filled with random data
xmit_data = tuple((i * 17) & 0xff for i in range(xmit_buf_size))
test_state.write_mem(xmit_buf_addr, xmit_data)

csr7.write(0x0001afef) # enable all interrupts
csr4.write(xmit_desc_addr)

# Start transmission
csr6.write(pr = 0, ps = 1, st = 1)

sent_frame = xmit_data + (0, 0, 0, 0)

# Look at the status register - interrupts expected
expect_equal(csr5.read() & 0x007fafef, 6 << 20 | Csr5.value(nis=1, tu=1, ti=1))

# Acknowledge the interrupt by clearing the flags
csr5.write(csr5.read() | 0xfff)

# Expect transmission of the data to have occurred, and an interrupt
expect_equal(test_state.seq,
       [('send_frame', sent_frame, 1),
        ('raise', conf.eth, 0),
        ('clear', conf.eth, 0)])

# Test frame reception

# Set up descriptors in memory:
# Make a single descriptor with a single buffer
recv_desc_addr = 0x7569abc0
recv_buf_size = 1600
recv_buf_addr = 0x14cd1800

# Map a Receive_desc on our test memory at recv_desc_addr
recv_desc = dev_util.Layout_LE(test_state.memory, recv_desc_addr, Receive_desc)
recv_desc.rdes0.write(0, own = 1)
recv_desc.rdes1.write(0, rer = 1, rbs1 = recv_buf_size)
recv_desc.buf_addr1 = recv_buf_addr
recv_desc.buf_addr2 = 0xa5a5a5a5

csr3.write(recv_desc_addr)

# Turn off transmission and start reception
csr6.write(st = 0, sr = 1)

# Make some data to send to the device
recv_size = 169
recv_data = tuple((i * 113) & 0xff for i in range(recv_size))

# The device is now waiting for frames. Send it one.
mac_if = conf.eth.iface.ieee_802_3_mac
mac_if.receive_frame(0, bytes(recv_data), 1)

# Examine the receive  descriptor status
expect_equal(recv_desc.rdes0.fs, 1)
expect_equal(recv_desc.rdes0.ls, 1)
expect_equal(recv_desc.rdes0.fl, recv_size)

# Examine memory to see that the right bytes have been written
expect_equal(tuple(test_state.read_mem(recv_buf_addr, recv_size)), recv_data)
