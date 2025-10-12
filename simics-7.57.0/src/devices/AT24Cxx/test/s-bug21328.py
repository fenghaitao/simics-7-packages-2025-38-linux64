# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Testing of bug21328 fix, which added support of AT24C32/64/128/256/512/M01

import pyobj
import stest
import random


# Fake I2C link
class fake_link(pyobj.ConfObject):
    '''Fake I2C link v2 class'''
    def _initialize(self):
        super()._initialize()
        self.acks = []
        self.resp = []
    class i2c_master_v2(pyobj.Interface):
        def finalize(self):
            pass
        def acknowledge(self, ack):
            self._up.acks.append(ack)
        def read_response(self, var):
            self._up.resp.append(var)

class at24cxx_test:
    '''helper class for AT24Cxx device tests'''

    def init(self, mem):
        self.mem = mem
        self.mem_len = len(mem)
        self.i2c_link = pre_conf_object('i2c_link%d' % self.mem_len, 'fake_link')
        self.i2c_slave = pre_conf_object('i2c_slave%d' % self.mem_len, 'AT24Cxx')
        # For some devices, ex. AT24C04/08/16/M01, device address contains
        # memory page address at the least bits. So 0x57 is invalid for AT24CM01.
        self.slave_address = 0x56
        self.i2c_slave.memory = mem
        self.i2c_slave.i2c_address = self.slave_address
        self.i2c_slave.i2c_link_v2 = self.i2c_link
        SIM_add_configuration([self.i2c_slave, self.i2c_link], None)
        self.i2c_slave = getattr(conf, 'i2c_slave%d' % self.mem_len)
        self.i2c_link = getattr(conf, 'i2c_link%d' % self.mem_len)

    def check_ack_message(self, expected):
        # Make sure the message is the new added and the only one
        stest.expect_equal(len(self.i2c_link.object_data.acks), 1)
        stest.expect_equal(self.i2c_link.object_data.acks.pop(), expected)

    def checked_resp_message(self):
        # Responded message after length-is-one checking
        stest.expect_true(len(self.i2c_link.object_data.resp) >= 1)
        return self.i2c_link.object_data.resp.pop()

    # Update device address and byte address based on device type
    def address_adaptation(self, addr):
        i2c_address = self.slave_address
        byte_addr = addr & 0xffff
        if len(self.mem) == 2 ** 17:
            if addr >= 2 ** 16:
                i2c_address = i2c_address | 0x01

        return (i2c_address, byte_addr)

    # random write and read with double address bytes
    def i2c_write_byte(self, addr, val):
        (i2c_addr, byte_addr) = self.address_adaptation(addr)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(val)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.stop()

    def i2c_read_byte(self, addr):
        (i2c_addr, byte_addr) = self.address_adaptation(addr)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1 | 0x01)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.read() # No ACK in read phase
        self.i2c_slave.iface.i2c_slave_v2.stop()
        return self.checked_resp_message()

    # Sequential read/write
    def i2c_write_page_bytes(self, addr, val):
        (i2c_addr, byte_addr) = self.address_adaptation(addr)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
        self.check_ack_message(0)
        for v in val:
            self.i2c_slave.iface.i2c_slave_v2.write(v)
            self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.stop()

    def i2c_read_page_bytes(self, addr, length):
        (i2c_addr, byte_addr) = self.address_adaptation(addr)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
        self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1 | 0x01)
        self.check_ack_message(0)
        val = []
        for i in range(length):
            self.i2c_slave.iface.i2c_slave_v2.read() # No ACK in read phase
            val.append(self.checked_resp_message())
        self.i2c_slave.iface.i2c_slave_v2.stop()
        return val

    # Repeated read/write
    def i2c_write_byte_repeated(self, addr, val, num):
        for i in range(num):
            (i2c_addr, byte_addr) = self.address_adaptation(addr + i)
            self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.write(val)
            self.check_ack_message(0)
        self.i2c_slave.iface.i2c_slave_v2.stop()

    def i2c_read_byte_repeated(self, addr, val, num):
        for i in range(num):
            (i2c_addr, byte_addr) = self.address_adaptation(addr + i)
            self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.write(byte_addr >> 8)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.write(byte_addr & 0xff)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.start(i2c_addr << 1 | 0x01)
            self.check_ack_message(0)
            self.i2c_slave.iface.i2c_slave_v2.read() # No ACK in read phase
        self.i2c_slave.iface.i2c_slave_v2.stop()
        for i in range(num):
            stest.expect_equal(self.checked_resp_message(), val)

    def test_basic_random_rdwr(self, addr):
        # Make sure acks/resp buffers of i2c_link are empty
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)

        for p in addr:
            p_mem = p % self.mem_len
            p_data = self.mem[p_mem]
            stest.expect_equal(self.i2c_read_byte(p), p_data)
            self.i2c_write_byte(p, p_data ^ 0x5a)
            stest.expect_equal(self.i2c_read_byte(p), p_data ^ 0x5a)
            self.i2c_write_byte(p, p_data)

        # Make sure acks/resp buffers of i2c_link are empty again
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)

    def test_sequential_write(self, addr, cnt):
        '''The address roll over during write is from the last byte
           of the current page to the first byte of the same page.
           If more than 32(page size) data words are transmitted
           to the EEPROM, the data word address will roll over and
           previous data will be overwritten.'''
        some_data = [x & 0xff for x in range(cnt)]
        # Make sure acks/resp buffers of i2c_link are empty
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)

        psize = self.i2c_slave.page_size
        pstart = addr & ~(psize - 1)
        data = self.i2c_read_page_bytes(pstart, psize)
        self.i2c_write_page_bytes(addr, some_data)
        pdata = self.i2c_read_page_bytes(pstart, psize)
        for i in range(cnt):
            data[(addr + i) % psize] = some_data[i]
        stest.expect_equal(data, pdata)

        # Make sure acks/resp buffers of i2c_link are empty again
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)

    def test_sequential_read(self, addr, cnt):
        '''The address roll over during read is from the last byte
           of the last memory page, to the first byte of the first page.'''
        # Make sure acks/resp buffers of i2c_link are empty
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)
        l = len(self.mem)
        a1 = addr % l
        a2 = (addr + cnt) % l
        if addr // l == (addr + cnt) // l:
            ll = list(self.mem[a1:a2])
        else:
            ll = list(self.mem[a1:l]) + list(self.mem[0:a2])
        stest.expect_equal(self.i2c_read_page_bytes(addr, cnt), ll)
        # Make sure acks/resp buffers of i2c_link are empty again
        stest.expect_false(self.i2c_link.object_data.acks)
        stest.expect_false(self.i2c_link.object_data.resp)

    def test_sequential_access(self):
        psize = self.i2c_slave.page_size
        mem_size = len(self.mem)
        self.test_sequential_read(0, psize)
        self.test_sequential_read(0, 2*psize)
        self.test_sequential_read(psize - 1, psize)
        self.test_sequential_read(mem_size - psize, psize)
        self.test_sequential_read(mem_size - psize + 1, psize + 1)
        self.test_sequential_write(0, psize)
        self.test_sequential_write(0, 2*psize)
        self.test_sequential_write(psize - 1, psize)
        self.test_sequential_write(mem_size - psize, psize)
        self.test_sequential_write(mem_size - psize + 1, psize + 1)

    def test_repeated_access(self):
        n = 3
        p = 0x11
        p_data = 0x55
        self.i2c_write_byte_repeated(p, p_data, n)
        self.i2c_read_byte_repeated(p, p_data, n)

    def test_random_access(self):
        mem_size = len(self.mem)
        addr = [random.randrange(2*mem_size) for i in range(8)]
        self.test_basic_random_rdwr(addr)


def memory_data(length):
    return tuple([i & 0xff ^ 0x3c for i in range(length)])


#  The number of bytes on the total memory size
#  AT24C32  :   4096
#  AT24C64  :   8192
#  AT24C128 :  16384
#  AT24C256 :  32768
#  AT24C512 :  65536
#  AT24CM01 : 131072

at24c32 = at24cxx_test()
at24c32.init(memory_data(4096))
at24c32.test_random_access()
at24c32.test_sequential_access()
at24c32.test_repeated_access()

at24c64 = at24cxx_test()
at24c64.init(memory_data(8192))
at24c64.test_random_access()
at24c64.test_sequential_access()
at24c64.test_repeated_access()

at24c128 = at24cxx_test()
at24c128.init(memory_data(16384))
at24c128.test_random_access()
at24c128.test_sequential_access()
at24c128.test_repeated_access()

at24c256 = at24cxx_test()
at24c256.init(memory_data(32768))
at24c256.test_random_access()
at24c256.test_sequential_access()
at24c256.test_repeated_access()

at24c512 = at24cxx_test()
at24c512.init(memory_data(65536))
at24c512.test_random_access()
at24c512.test_sequential_access()
at24c512.test_repeated_access()

at24cm01 = at24cxx_test()
at24cm01.init(memory_data(131072))
at24cm01.test_random_access()
at24cm01.test_sequential_access()
at24cm01.test_repeated_access()

print("passed: s-bug21328")
