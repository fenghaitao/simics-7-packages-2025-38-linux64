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


import simics
import stest
import conf
import dev_util
import spi_master
import contextlib

CMD_WREN            = 0x06
CMD_WRDI            = 0x04
CMD_RDSR            = 0x05
CMD_WRSR            = 0x01
CMD_WRLR            = 0xe5
CMD_RDLR            = 0xe8
CMD_READ            = 0x03
CMD_FREAD           = 0x0b
CMD_FP_QUAD_I       = 0x32
CMD_FP_QUAD_I_V2    = 0x38
CMD_FREAD_DUAL_O    = 0x3b
CMD_FREAD_DUAL_IO    = 0xbb
CMD_FREAD_QUAD_O    = 0x6b
CMD_FREAD_QUAD_IO   = 0xeb
CMD_PW              = 0x0a
CMD_PP              = 0x02
CMD_FP_DUAL_I       = 0xa2
CMD_PE              = 0xdb
CMD_SSE             = 0x20
CMD_SE              = 0xd8
CMD_BE              = 0xc7
CMD_CE              = 0x60
CMD_DE              = 0xc4
CMD_DP              = 0xb9
CMD_RES             = 0xab
CMD_RDID            = 0x9f
CMD_RDMID           = 0x90

CMD_RDFSR           = 0x70
CMD_RDEAR           = 0xc8
CMD_WREAR           = 0xc5

CMD_EN4B            = 0xb7
CMD_EX4B            = 0xe9

CMD_READ4           = 0x13
CMD_FREAD4          = 0xc
CMD_FREAD4_DUAL_O   = 0x3c
CMD_FREAD4_QUAD_O   = 0x6c
CMD_FREAD4_QUAD_IO  = 0xec

CMD_PP_4B           = 0x12
CMD_FP_4B_QUAD_I    = 0x34

CMD_SE_4B           = 0xdc
CMD_SSE_4B          = 0x21

CMD_32BE            = 0x52
CMD_32BE_4B         = 0x5c

CMD_ENQD            = 0x35
CMD_RSTQD           = 0xf5

CMD_WRENHV          = 0x61
CMD_RDENHV          = 0x65

CMD_RSFDP           = 0x5a

CMD_WRBRV           = 0x17
CMD_WRBRNV          = 0x18

class TestBench:
    def __init__(self,
                 sector_size     = 0x10000,
                 sector_number   = 16,
                 elec_signature  = 0x13,
                 JEDEC_signature = None,
                 extended_id     = None,
                 frdo_enabled    = False,
                 frqo_enabled    = False,
                 fpdi_enabled    = False,
                 fpqi_enabled    = False,
                 addr4b_enabled  = False,
                 dual_parallel_enabled = False):

        self.flash_size      = sector_size * sector_number
        self.bp_mask         = (3 if (sector_number <= 4) else
                                15 if (sector_number > 128) else 7)
        self.sector_size     = sector_size
        self.sector_number   = sector_number
        self.elec_signature  = elec_signature
        self.JEDEC_signature = JEDEC_signature
        self.extended_id     = extended_id
        self.frdo_enabled    = frdo_enabled
        self.frqo_enabled    = frqo_enabled
        self.fpdi_enabled    = fpdi_enabled
        self.fpqi_enabled    = fpqi_enabled
        self.addr4b_enabled  = addr4b_enabled
        self.dual_parallel_enabled = dual_parallel_enabled

        if dual_parallel_enabled:
            self.flash_size = self.flash_size << 1

        # Flash Image
        self.image = simics.pre_conf_object('image', 'image')
        self.image.size = self.flash_size
        simics.SIM_add_configuration([self.image], None)
        self.image = conf.image

        # Flash
        self.flash = simics.pre_conf_object('flash', 'M25Pxx')
        self.flash.mem_block = self.image
        self.flash.elec_signature = self.elec_signature
        self.flash.sector_size = self.sector_size
        self.flash.sector_number = self.sector_number
        if self.JEDEC_signature:
            self.flash.JEDEC_signature = self.JEDEC_signature
        if self.extended_id:
            self.flash.extended_id = self.extended_id
        self.flash.frdo_enabled = self.frdo_enabled
        self.flash.frqo_enabled = self.frqo_enabled
        self.flash.fpdi_enabled = self.fpdi_enabled
        self.flash.fpqi_enabled = self.fpqi_enabled
        self.flash.addr4b_enabled = self.addr4b_enabled
        self.flash.dual_parallel_enabled = self.dual_parallel_enabled
        simics.SIM_add_configuration([self.flash], None)
        self.flash = conf.flash

        # Master
        self.master = simics.SIM_create_object('SPIMaster', 'master')

        # SPI checker
        self.checker = simics.SIM_create_object('spi_checker', 'checker',
                                                [['slave', self.flash]])
        self.master.slave = self.checker
        self.slave_iface = self.master.iface.serial_peripheral_interface_slave

    @contextlib.contextmanager
    def addr4b(self):
        enabled = self.addr4b_enabled
        self.addr4b_enabled = True
        try:
            yield
        finally:
            self.addr4b_enabled = enabled

    def send_data(self, bits, payload, first=0, last=0):
        payload = bytes(payload)
        self.slave_iface.spi_request(first, last, bits, payload)

    def receive_data(self, bits, first=0, last=0):
        payload = b'\0' * ((bits + 7) // 8)
        self.slave_iface.spi_request(first, last, bits, payload)
        return self.master.payload

    def connect_slave(self, flag=1):
        self.slave_iface.connect_master(self.master, None, flag)

    def disconnect_slave(self, flag=1):
        self.slave_iface.disconnect_master(self.master)

    def expect(self, expr, usage, result=True):
        if result:
            stest.expect_true(expr, 'unexpected %s mismatch' % usage)
        else:
            stest.expect_false(expr, 'unexpected %s match' % usage)

    def write_flash_status(self, status):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(16, [CMD_WRSR, status], first=1, last=1)
        self.disconnect_slave()

    def read_flash_status(self):
        self.connect_slave()
        self.send_data(8, [CMD_RDSR], first=1)
        data = self.receive_data(8, last=1)
        self.disconnect_slave()
        return data[0]

    def get_addr(self, disk_addr):
        if self.addr4b_enabled:
            addr = [(disk_addr >> bits) & 0xff for bits in [24, 16, 8, 0]]
            addr_bits = 32
        else:
            addr = [(disk_addr >> bits) & 0xff for bits in [16, 8, 0]]
            addr_bits = 24
        return (addr, addr_bits)

    def write_flash_lock(self, sector, lock):
        disk_addr = self.sector_size * sector
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8 + addr_bits, [CMD_WRLR] + addr, first=1)
        self.send_data(8, [lock], last=1)
        self.disconnect_slave()

    def read_flash_lock(self, sector):
        disk_addr = self.sector_size * sector
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits, [CMD_RDLR] + addr, first=1)
        data = self.receive_data(8, last=1)
        self.disconnect_slave()
        return data[0]

    def read_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits, [CMD_READ] + addr, first=1)
        data = self.receive_data(8 * length, last=1)
        self.disconnect_slave()
        return data

    def fread_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits + 8, [CMD_FREAD] + addr + [0], first = 1)
        data = self.receive_data(length * 8, last = 1)
        self.disconnect_slave()
        return data

    def fread_dual_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits + 8, [CMD_FREAD_DUAL_O] + addr + [0], first = 1)
        data = self.receive_data(length * 8, last = 1)
        self.disconnect_slave()
        return data

    def fread_dual_io_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits + 8, [CMD_FREAD_DUAL_IO] + addr + [0], first = 1)
        data = self.receive_data(length * 8, last = 1)
        self.disconnect_slave()
        return data

    def fread_quad_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits + 8, [CMD_FREAD_QUAD_O] + addr + [0], first = 1)
        data = self.receive_data(length * 8, last = 1)
        self.disconnect_slave()
        return data

    def fread_quad_io_flash_data(self, disk_addr, length):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8 + addr_bits + 8, [CMD_FREAD_QUAD_IO] + addr + [0], first = 1)
        data = self.receive_data(length * 8, last = 1)
        self.disconnect_slave()
        return data

    def program_flash(self, disk_addr, data):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_PP], first=1)
        self.send_data(addr_bits, addr)
        self.send_data(len(data) * 8, data, last=1)
        self.disconnect_slave()

    def dual_fast_program_flash(self, disk_addr, data):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_FP_DUAL_I], first=1)
        self.send_data(addr_bits, addr)
        self.send_data(len(data) * 8, data, last=1)
        self.disconnect_slave()

    def quad_fast_program_flash(self, disk_addr, data):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_FP_QUAD_I], first=1)
        self.send_data(addr_bits, addr)
        self.send_data(len(data) * 8, data, last=1)
        self.disconnect_slave()

    def quad_fast_program_flash_v2(self, disk_addr, data):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_FP_QUAD_I_V2], first=1)
        self.send_data(addr_bits, addr)
        self.send_data(len(data) * 8, data, last=1)
        self.disconnect_slave()

    def program_flash_common(self, disk_addr, data):
        self.program_flash(disk_addr, data)
        if (self.flash.fpdi_enabled):
            self.dual_fast_program_flash(disk_addr, data)

        if (self.flash.fpqi_enabled):
            self.quad_fast_program_flash(disk_addr, data)
            self.quad_fast_program_flash_v2(disk_addr, data)

    def page_write_flash(self, disk_addr, data):
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_PW], first=1)
        self.send_data(addr_bits, addr)
        self.send_data(len(data) * 8, data, last=1)
        self.disconnect_slave()

    def page_erase_flash(self, page):
        page_size = 512 if self.flash.dual_parallel_enabled else 256
        disk_addr = page_size * page
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_PE], first=1)
        self.send_data(addr_bits, addr, last=1)
        self.disconnect_slave()

    def subsector_erase_flash(self, sector):
        disk_addr = self.sector_size // 16 * sector
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_SSE], first=1)
        self.send_data(addr_bits, addr, last=1)
        self.disconnect_slave()

    def sector_erase_flash(self, sector):
        disk_addr = self.sector_size * sector
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_SE], first=1)
        self.send_data(addr_bits, addr, last=1)
        self.disconnect_slave()

    def block_erase_32KB(self, sector):
        disk_addr = 32768 * sector
        (addr, addr_bits) = self.get_addr(disk_addr)
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_32BE], first=1)
        self.send_data(addr_bits, addr, last=1)
        self.disconnect_slave()

    def block_erase_32KB_4b(self, sector):
        with self.addr4b():
            disk_addr = 32768 * sector
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8, [CMD_WREN], first=1, last=1)
            self.send_data(8, [CMD_32BE_4B], first=1)
            self.send_data(addr_bits, addr, last=1)
            self.disconnect_slave()

    def bulk_erase_flash(self):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_BE], first=1, last=1)
        self.disconnect_slave()

    def chip_erase_flash(self):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_CE], first=1, last=1)
        self.disconnect_slave()

    def die_erase_flash(self):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(8, [CMD_DE], first=1, last=1)
        self.disconnect_slave()

    def clear_image_data(self):
        self.image.iface.image.clear_range(0, self.flash_size)

    def clear_protection_bits(self):
        status = self.read_flash_status()
        self.write_flash_status(status & 0xe3)

    def clear_sector_lock(self):
        for i in range(self.sector_number * 16):
            self.write_flash_lock(i, 0)

    def write_extend_address(self, ext_addr):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(16, [CMD_WREAR, ext_addr], first=1, last=1)
        self.disconnect_slave()

    def read_extend_address(self):
        self.connect_slave()
        self.send_data(8, [CMD_RDEAR], first=1)
        data = self.receive_data(8, last=1)
        self.disconnect_slave()
        return data[0]

    def read_flag_status(self):
        self.connect_slave()
        self.send_data(8, [CMD_RDFSR], first=1)
        data = self.receive_data(8, last=1)
        self.disconnect_slave()
        return data[0]

    def enter_quad_mode(self):
        self.connect_slave()
        self.send_data(8, [CMD_ENQD], first=1, last=1)
        self.disconnect_slave()

    def exit_quad_mode(self):
        self.connect_slave()
        self.send_data(8, [CMD_RSTQD], first=1, last=1)
        self.disconnect_slave()

    def enter_4b_address_mode(self):
        self.connect_slave()
        self.send_data(8, [CMD_EN4B], first=1, last=1)
        self.disconnect_slave()

    def exit_4b_address_mode(self):
        self.connect_slave()
        self.send_data(8, [CMD_EX4B], first=1, last=1)
        self.disconnect_slave()

    def read_flash_data_4b(self, disk_addr, length):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8 + addr_bits, [CMD_READ4] + addr, first = 1)
            data = self.receive_data(length * 8, last = 1)
            self.disconnect_slave()
            return data

    def fread_flash_data_4b(self, disk_addr, length):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8 + addr_bits + 8, [CMD_FREAD4] + addr + [0], first = 1)
            data = self.receive_data(length * 8, last = 1)
            self.disconnect_slave()
            return data

    def fread_dual_flash_data_4b(self, disk_addr, length):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8 + addr_bits + 8, [CMD_FREAD4_DUAL_O] + addr + [0], first = 1)
            data = self.receive_data(length * 8, last = 1)
            self.disconnect_slave()
            return data

    def fread_quad_flash_data_4b(self, disk_addr, length):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8 + addr_bits + 8, [CMD_FREAD4_QUAD_O] + addr + [0], first = 1)
            data = self.receive_data(length * 8, last = 1)
            self.disconnect_slave()
            return data

    def fread_quad_io_flash_data_4b(self, disk_addr, length):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8 + addr_bits + 8, [CMD_FREAD4_QUAD_IO] + addr + [0], first = 1)
            data = self.receive_data(length * 8, last = 1)
            self.disconnect_slave()
            return data

    def program_flash_4b(self, disk_addr, data):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8, [CMD_WREN], first=1, last=1)
            self.send_data(8, [CMD_PP_4B], first=1)
            self.send_data(addr_bits, addr)
            self.send_data(len(data) * 8, data, last=1)
            self.disconnect_slave()

    def quad_fast_program_flash_4b(self, disk_addr, data):
        with self.addr4b():
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8, [CMD_WREN], first=1, last=1)
            self.send_data(8, [CMD_FP_4B_QUAD_I], first=1)
            self.send_data(addr_bits, addr)
            self.send_data(len(data) * 8, data, last=1)
            self.disconnect_slave()

    def program_flash_common_4b(self, disk_addr, data):
        self.program_flash_4b(disk_addr, data)
        if (self.flash.fpqi_enabled):
            self.quad_fast_program_flash_4b(disk_addr, data)

    def subsector_erase_flash_4b(self, sector):
        with self.addr4b():
            disk_addr = self.sector_size // 16 * sector
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8, [CMD_WREN], first=1, last=1)
            self.send_data(8, [CMD_SSE_4B], first=1)
            self.send_data(addr_bits, addr, last=1)
            self.disconnect_slave()

    def sector_erase_flash_4b(self, sector):
        with self.addr4b():
            disk_addr = self.sector_size * sector
            (addr, addr_bits) = self.get_addr(disk_addr)
            self.connect_slave()
            self.send_data(8, [CMD_WREN], first=1, last=1)
            self.send_data(8, [CMD_SE_4B], first=1)
            self.send_data(addr_bits, addr, last=1)
            self.disconnect_slave()

    def read_sfdp_data(self, addr, length):
        self.connect_slave()
        self.send_data(5 * 8, [CMD_RSFDP, 0, 0, addr & 0xff, 0], first=1)
        data = self.receive_data(length * 8, last=1)
        self.disconnect_slave()
        return data

    def test_elec_signature(self, expected=None, result=True):
        expect = expected or self.elec_signature

        self.connect_slave()
        self.send_data(32, [CMD_RES, 0, 0, 0], first = 1)
        for i in range(10):
            data = self.receive_data(8, last=(1, 0)[i < 9])
            self.expect(data[0] == expect, 'Electronic Signature', result)
        self.disconnect_slave()

    def test_jedec_id(self, expected=None, result=True):
        if not self.JEDEC_signature:
            return
        len = 3 * 8
        expect = expected or self.JEDEC_signature
        if self.extended_id:
            len = 5 * 8
            expect = expected or (self.JEDEC_signature + self.extended_id)

        self.connect_slave()
        self.send_data(8, [CMD_RDID], first=1)
        data = self.receive_data(len, last = 1)
        self.disconnect_slave()
        self.expect(data == tuple(expect), 'JEDEC Signature', result)

    def test_rmdid(self, expected=None, result=True):
        if not self.JEDEC_signature:
            return
        expect = expected or (self.JEDEC_signature[0], self.elec_signature)

        self.connect_slave()
        self.send_data(4 * 8, [CMD_RDMID, 0, 0, 0], first=1)
        data = self.receive_data(2 * 8, last = 1)
        self.disconnect_slave()
        self.expect(data == tuple(expect), 'RDMID data', result)

    def test_flash_status(self):
        bp = 0x5
        status = self.read_flash_status()
        status &= 0xe3
        status |= (bp << 2)
        self.write_flash_status(status)
        status = self.read_flash_status()
        self.expect(
            (bp & self.bp_mask) == ((status >> 2) & 7), 'BP value', True)

    def test_read_write_flash(self, addr=0, data=None):
        self.clear_protection_bits()

        if data:
            assert addr < self.sector_size * self.sector_number
            raise Exception('Not supported now')

        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        for i in range(0, self.sector_number, step):
            for aligned in [0x80, 0x100]:
                data = [(i * 16 + j) & 0xff for j in range(32)]
                self.sector_erase_flash(i)
                self.program_flash_common(self.sector_size * i + aligned, data)

                rdata = self.read_flash_data(self.sector_size * i + aligned,
                                             32)
                self.expect(tuple(data) == rdata, 'Program/Read Flash data')

                rdata = self.fread_flash_data(self.sector_size * i + aligned,
                                              32)
                self.expect(tuple(data) == rdata, 'Program/FRead Flash data')

                if (self.flash.frdo_enabled):
                    rdata = self.fread_dual_flash_data(self.sector_size * i + aligned, 32)
                    self.expect(tuple(data) == rdata, 'Program/FRead Dual Flash data')
                    rdata = self.fread_dual_io_flash_data(self.sector_size * i + aligned, 32)
                    self.expect(tuple(data) == rdata, 'Program/FRead Dual I/O Flash data')

                if (self.flash.frqo_enabled):
                    rdata = self.fread_quad_flash_data(self.sector_size * i + aligned, 32)
                    self.expect(tuple(data) == rdata, 'Program/FRead Quad Flash data')
                    rdata = self.fread_quad_io_flash_data(self.sector_size * i + aligned, 32)
                    self.expect(tuple(data) == rdata, 'Program/FRead Quad I/O Flash data')

                # bug 21501, not possible to program bits to 1, 0xff is a NOP
                self.program_flash_common(self.sector_size * i + aligned,
                                          [0xff] * 32)
                rdata = self.read_flash_data(self.sector_size * i + aligned, 32)
                self.expect(tuple(data) == rdata, 'Program 0xff is a NOP')

    def test_page_write_flash(self, addr=0, data=None):
        self.clear_protection_bits()
        self.clear_image_data()

        if data:
            assert addr < self.sector_size * self.sector_number
            raise Exception('Not supported now')

        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        for i in range(0, self.sector_number, step):
            data = [(i * 16 + j) & 0xaa for j in range(32)]
            self.page_write_flash(self.sector_size * i + 0x100, data)

            rdata = self.read_flash_data(self.sector_size * i + 0x100, 32)
            self.expect(tuple(data) == rdata, 'Program/Read Flash data')

            rdata = self.fread_flash_data(self.sector_size * i + 0x100, 32)
            self.expect(tuple(data) == rdata, 'Program/FRead Flash data')

    def test_page_erase(self):
        self.clear_protection_bits()
        self.clear_image_data()
        psz = 512 if self.flash.dual_parallel_enabled else 256
        nps = self.sector_number * self.sector_size // psz
        odata = [0x00 for j in range(32)]
        edata = [0xff for j in range(32)]

        for i in range(0, nps, nps // 16):
            self.clear_image_data()
            self.page_erase_flash(i)
            data = self.read_flash_data(psz * i, 32)
            self.expect(tuple(edata) == data, 'Page Erased Data')

            data = self.read_flash_data(psz * ((i + 1) % nps), 32)
            self.expect(tuple(odata) == data, 'Page Non-Erased Data1')
            data = self.read_flash_data(psz * ((i - 1) % nps), 32)
            self.expect(tuple(odata) == data, 'Page Non-Erased Data2')

    def test_subsector_erase(self):
        self.clear_protection_bits()
        self.clear_image_data()
        ssz = self.sector_size // 16
        nss = self.sector_number * 16
        odata = [0x00 for j in range(32)]
        edata = [0xff for j in range(32)]

        for i in range(0, nss, nss // 16):
            self.clear_image_data()
            self.subsector_erase_flash(i)
            data = self.read_flash_data(ssz * i, 32)
            self.expect(tuple(edata) == data, 'Subsector Erased Data')

            data = self.read_flash_data(ssz * ((i + 1) % nss), 32)
            self.expect(tuple(odata) == data, 'Subsector Non-Erased Data1')
            data = self.read_flash_data(ssz * ((i - 1) % nss), 32)
            self.expect(tuple(odata) == data, 'Subsector Non-Erased Data2')

    def test_sector_erase(self):
        self.clear_protection_bits()
        self.clear_image_data()

        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        for i in range(0, self.sector_number, step):
            self.sector_erase_flash(i)
            data = [0xff for j in range(32)]
            edata = self.read_flash_data(self.sector_size * i, 32)
            self.expect(tuple(data) == edata, 'Sector Erase Data')

    def test_32KB_block_erase(self):
        self.clear_protection_bits()
        self.clear_image_data()

        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        all_one_data = (0xff, ) * 32
        for i in range(0, self.sector_number * 2, step * 2):
            self.block_erase_32KB(i)
            edata = self.fread_flash_data(32768 * i, 32)
            self.expect(all_one_data == edata, '32KB Block Erase')

    def test_32KB_block_erase_4b(self):
        self.clear_protection_bits()
        self.clear_image_data()

        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        all_one_data = (0xff, ) * 32
        for i in range(0, self.sector_number * 2, step * 2):
            self.block_erase_32KB_4b(i)
            edata = self.fread_flash_data(32768 * i, 32)
            self.expect(all_one_data == edata, '32KB Block Erase')

    def test_bulk_erase(self):
        self.clear_protection_bits()
        self.clear_image_data()

        self.bulk_erase_flash()
        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        for i in range(0, self.sector_number, step):
            data = [0xff for j in range(32)]
            edata = self.fread_flash_data(self.sector_size * i, 32)
            self.expect(tuple(data) == edata, 'Bulk Erase Data')

    def test_chip_erase(self):
        self.clear_protection_bits()
        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        all_one_data = (0xff, ) * 32

        self.clear_image_data()
        self.chip_erase_flash()
        for i in range(0, self.sector_number, step):
            edata = self.fread_flash_data(self.sector_size * i, 32)
            self.expect(all_one_data == edata, 'Chip Erase Data')

    def test_die_erase(self):
        self.clear_protection_bits()
        step = 1 if (self.sector_number // 16 == 0) else (self.sector_number // 16)
        all_one_data = (0xff, ) * 32
        self.clear_image_data()
        self.die_erase_flash()
        for i in range(0, self.sector_number, step):
            edata = self.fread_flash_data(self.sector_size * i, 32)
            self.expect(all_one_data == edata, 'Die Erase Data')

    def test_spm1_protection(self, prot_sector):
        self.clear_protection_bits()
        self.clear_sector_lock()
        self.clear_image_data()

        self.expect(self.read_flash_lock(prot_sector) == 0, 'Read Sector Lock')
        self.write_flash_lock(prot_sector, 1)
        self.expect(self.read_flash_lock(prot_sector) == 1, 'Write Sector Lock')

        edata = [0xff] * 32
        odata = [0] * 32
        for i in range(self.sector_number):
            self.sector_erase_flash(i)
            data = self.fread_flash_data(self.sector_size * i, 32)
            if i != prot_sector:
                self.expect(tuple(edata) == data, 'Erased data')
            else:
                self.expect(tuple(odata) == data, 'Non-erased data')
        self.clear_sector_lock()

        self.write_flash_lock(prot_sector, 3)
        self.write_flash_lock(prot_sector, 0)
        self.expect(self.read_flash_lock(prot_sector) == 3, 'SPM1 LR Lock Down')
        self.flash.ports.HRESET.signal.signal_raise()

    def test_program_protection(self, bp, prot_sector):
        self.clear_protection_bits()
        self.clear_image_data()

        for i in range(self.sector_number):
            data = [(x + i) % 256 for x in range(32)]
            self.sector_erase_flash(i)
            self.program_flash_common(self.sector_size * i, data)

        status = self.read_flash_status()
        status &= 0xe3
        status |= (bp << 2)
        self.write_flash_status(status)

        for i in range(self.sector_number):
            ndata = [0 for j in range(32)]
            odata = [(x + i) % 256 for x in range(32)]
            self.program_flash_common(self.sector_size * i, ndata)
            data = self.read_flash_data(self.sector_size * i, 32)
            if i < prot_sector:
                self.expect(data == tuple(ndata), 'Non-protected data')
            else:
                self.expect(data == tuple(odata), 'Protected data')

    def test_sector_protection(self, bp, prot_sector):
        self.clear_protection_bits()
        self.clear_image_data()

        status = self.read_flash_status()
        status &= 0xe3
        status |= bp << 2
        self.write_flash_status(status)

        for i in range(self.sector_number):
            self.sector_erase_flash(i)
            edata = [0xff for x in range(32)]
            odata = [0 for x in range(32)]
            data = self.fread_flash_data(self.sector_size * i, 32)
            if i < prot_sector:
                self.expect(tuple(edata) == data, 'Erased data')
            else:
                self.expect(tuple(odata) == data, 'Non-erased data')

    def test_operation_with_wrong_state(self, addr, data):
        # write data
        self.sector_erase_flash(addr // self.sector_size)
        self.program_flash_common(addr, data)

        # re-write command when protected
        data1 = [0xFF - x for x in data]
        stest.untrap_log('spec-viol')
        self.connect_slave()
        self.send_data(8, [CMD_WRDI], first=1)
        self.send_data(8, [CMD_PP])
        self.send_data(24, [(addr >> bits) & 0xff for bits in [16, 8, 0]])
        self.send_data(len(data1) * 8, data1, last=0)
        self.send_data(len(data1) * 8, data1, last=1)
        self.disconnect_slave()
        stest.trap_log('spec-viol')

        # verify the data hasn't been changed
        res = self.read_flash_data(addr, len(data))
        stest.expect_equal(list(res), data)

    def test_persistent(self):
        self.expect(self.image.iface.checkpoint.has_persistent_data(), 1)

    def test_read_write_with_extend_address(self):
        addr4b_enabled = self.addr4b_enabled
        addr = 0x100
        seg = 3
        edata = [i ^ 0x5a for i in range(32)]

        self.clear_protection_bits()
        self.chip_erase_flash()

        self.exit_4b_address_mode()
        self.addr4b_enabled = False
        self.write_extend_address(seg)
        self.program_flash_common(addr, edata)
        self.enter_4b_address_mode()
        self.addr4b_enabled = True
        rdata = self.read_flash_data_4b(addr + (seg << 24), 32)
        self.expect(tuple(edata) == rdata, "Write with Extend Address")

        self.chip_erase_flash()
        edata = [x ^ 0xa5 for x in edata]
        self.program_flash_common_4b(addr + (seg << 24), edata)
        self.exit_4b_address_mode()
        self.addr4b_enabled = False
        rdata = self.read_flash_data(addr, 32)
        self.expect(tuple(edata) == rdata, "Read with Extend Address")

        # Restore contexts to avoid making troubles for other tests
        self.addr4b_enabled = addr4b_enabled
        if addr4b_enabled:
            self.enter_4b_address_mode()
        else:
            self.exit_4b_address_mode()
        self.write_extend_address(0)

    def test_extend_address(self):
        ext_addr = self.read_extend_address()
        self.expect(ext_addr == 0x0, "Default extend address")
        self.write_extend_address(0x5a)
        ext_addr = self.read_extend_address()
        self.expect(ext_addr == 0x5a, "Set extend address")
        self.write_extend_address(0x0)
        ext_addr = self.read_extend_address()
        self.expect(ext_addr == 0x0, "Restore extend address")
        self.test_read_write_with_extend_address()

    def test_quad_mode_switch(self):
        if self.flash.fpqi_enabled or self.flash.frqo_enabled:
            self.exit_quad_mode()
            self.expect(not self.flash.fpqi_enabled, "Exit QUAD input mode")
            self.expect(not self.flash.frqo_enabled, "Exit QUAD output mode")
            self.test_read_write_flash_4b()
            self.enter_quad_mode()
            self.expect(self.flash.fpqi_enabled, "Enter QUAD input mode")
            self.expect(self.flash.frqo_enabled, "Enter QUAD output mode")
            self.test_read_write_flash_4b()
        else:
            self.enter_quad_mode()
            self.expect(self.flash.fpqi_enabled, "Enter QUAD input mode")
            self.expect(self.flash.frqo_enabled, "Enter QUAD output mode")
            self.test_read_write_flash_4b()
            self.exit_quad_mode()
            self.expect(not self.flash.fpqi_enabled, "Exit QUAD input mode")
            self.expect(not self.flash.frqo_enabled, "Exit QUAD output mode")
            self.test_read_write_flash_4b()

    def test_write_bank_address_volatile(self):
        self.connect_slave()
        self.send_data(16, [CMD_WRBRV, 0x81], first=1, last=1)
        self.disconnect_slave()
        addr_mode = self.read_flag_status() & 0x1
        ext_addr = self.read_extend_address()
        self.expect(addr_mode == 0x1, "Enter 4B address mode")
        self.expect(ext_addr == 0x1, "Set extend address")

        self.connect_slave()
        self.send_data(16, [CMD_WRBRV, 0x0], first=1, last=1)
        self.disconnect_slave()
        addr_mode = self.read_flag_status() & 0x1
        ext_addr = self.read_extend_address()
        self.expect(addr_mode == 0x0, "Exit 4B address mode")
        self.expect(ext_addr == 0x0, "Unset extend address")

    def test_write_bank_address_non_volatile(self):
        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(16, [CMD_WRBRNV, 0x81], first=1, last=1)
        self.disconnect_slave()
        addr_mode = self.read_flag_status() & 0x1
        ext_addr = self.read_extend_address()
        self.expect(addr_mode == 0x1, "Enter 4B address mode")
        self.expect(ext_addr == 0x1, "Set extend address")

        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(16, [CMD_WRBRNV, 0x0], first=1, last=1)
        self.disconnect_slave()
        addr_mode = self.read_flag_status() & 0x1
        ext_addr = self.read_extend_address()
        self.expect(addr_mode == 0x0, "Exit 4B address mode")
        self.expect(ext_addr == 0x0, "Unset extend address")

    def test_4b_address_mode_switch(self):
        addr_mode = self.read_flag_status() & 0x1
        if addr_mode == 0:
            self.enter_4b_address_mode()
            addr_mode = self.read_flag_status() & 0x1
            self.expect(addr_mode == 0x1, "Enter 4B address mode")
            self.exit_4b_address_mode()
            addr_mode = self.read_flag_status() & 0x1
            self.expect(addr_mode == 0x0, "Exit 4B address mode")
        else:
            self.exit_4b_address_mode()
            addr_mode = self.read_flag_status() & 0x1
            self.expect(addr_mode == 0x0, "Exit 4B address mode")
            self.enter_4b_address_mode()
            addr_mode = self.read_flag_status() & 0x1
            self.expect(addr_mode == 0x1, "Enter 4B address mode")

    def test_read_write_flash_4b(self):
        self.clear_protection_bits()
        addr_mode_before = self.read_flag_status() & 0x1

        for i in range(0, self.sector_number, self.sector_number // 16):
            data = [(i * 16 + j) & 0xff for j in range(32)]
            self.sector_erase_flash_4b(i)
            self.program_flash_common_4b(self.sector_size * i + 0x100, data)

            rdata = self.read_flash_data_4b(self.sector_size * i + 0x100, 32)
            self.expect(tuple(data) == rdata, 'Program/Read Flash data 4B')

            rdata = self.fread_flash_data_4b(self.sector_size * i + 0x100, 32)
            self.expect(tuple(data) == rdata, 'Program/FRead Flash data 4B')

            if (self.flash.frdo_enabled):
                rdata = self.fread_dual_flash_data_4b(self.sector_size * i + 0x100, 32)
                self.expect(tuple(data) == rdata, 'Program/FRead Dual Flash data 4B')

            if (self.flash.frqo_enabled):
                rdata = self.fread_quad_flash_data_4b(self.sector_size * i + 0x100, 32)
                self.expect(tuple(data) == rdata, 'Program/FRead Quad Flash data 4B')
                rdata = self.fread_quad_io_flash_data_4b(self.sector_size * i + 0x100, 32)
                self.expect(tuple(data) == rdata, 'Program/FRead Quad IO Flash data 4B')

        addr_mode_after = self.read_flag_status() & 0x1
        self.expect(addr_mode_after == addr_mode_before, 'Keep address mode')

    def test_subsector_erase_4b(self):
        self.clear_protection_bits()
        self.clear_image_data()
        ssz = self.sector_size // 16
        nss = self.sector_number * 16
        odata = [0x00 for j in range(32)]
        edata = [0xff for j in range(32)]

        for i in range(0, nss, self.sector_number):
            self.clear_image_data()
            self.subsector_erase_flash_4b(i)
            data = self.read_flash_data_4b(ssz * i, 32)
            self.expect(tuple(edata) == data, 'Subsector Erased Data')

            data = self.read_flash_data_4b(ssz * ((i + 1) % nss), 32)
            self.expect(tuple(odata) == data, 'Subsector Non-Erased Data1')
            data = self.read_flash_data_4b(ssz * ((i - 1) % nss), 32)
            self.expect(tuple(odata) == data, 'Subsector Non-Erased Data2')

    def test_sector_erase_4b(self):
        self.clear_protection_bits()
        self.clear_image_data()

        for i in range(0, self.sector_number, self.sector_number // 16):
            self.sector_erase_flash_4b(i)
            data = [0xff for j in range(32)]
            edata = self.read_flash_data_4b(self.sector_size * i, 32)
            self.expect(tuple(data) == edata, 'Sector Erase Data')

    def test_dual_parallel_mode_switch(self):
        self.flash.dual_parallel_enabled = True
        self.expect(self.flash.sector_size == (self.sector_size << 1),
                    'Sector size in dual parallel mode')
        self.flash.dual_parallel_enabled = False
        self.expect(self.flash.sector_size == self.sector_size,
                    'Sector size in normal mode')
        # restore default configuration
        self.flash.dual_parallel_enabled = self.dual_parallel_enabled

    def test_cmd_counter(self):
        self.flash.fcmd_counter[CMD_BE] = 0
        self.bulk_erase_flash()
        self.expect(self.flash.fcmd_counter[CMD_BE] == 1, "Command Counter")

    def test_read_write_enhanced_volatile_conf_register(self):
        data = 0x00  # only bit 7 function is implemented

        self.connect_slave()
        self.send_data(8, [CMD_WREN], first=1, last=1)
        self.send_data(16, [CMD_WRENHV, data], first=1, last=1)
        self.disconnect_slave()

        self.connect_slave()
        self.send_data(8, [CMD_RDENHV], first=1)
        rdata = self.receive_data(8, last=1)
        self.disconnect_slave()

        self.expect(data == rdata[0],
                    "Read/Write Enhanced volatile Configuration Register")

    def test_rsfdp(self):
        signature = list(map(ord, ['S', 'F', 'D', 'P']))
        rdata = self.read_sfdp_data(0, 4)
        self.expect(tuple(signature) == rdata, "Read SFDP data")

        header2 = (8, 1, 0, 0xff)
        rdata = self.read_sfdp_data(4, 4)
        stest.expect_equal(header2, rdata, "Read SFDP header second word")
