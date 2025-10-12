# test_shell.py
# Definitions some functions of test for I82559

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


from common   import *
from cmd_defs import *
import simics

pci_registers = {
    #name             : [offset,    size,   r/w,   mask,   default value]
    "VENDOR_ID"       : [0x0,  2,  "RW",   0xFFFF,      0x8086    ],
    "DEVICE_ID"       : [0x2,  2,  "RW",   0xFFFF,      0x1229    ],
    "PCI_COMMAND"     : [0x4,  2,  "RW",   0xFFFF,      0x0       ],
    "PCI_STATUS"      : [0x6,  2,  "RW",   0xFFFF,      0x0       ],
    "REVISION"        : [0x8,  1,  "RW",   0xFF,        0x9       ],
    "CLASS_CODE"      : [0x9,  3,  "RW",   0xFFFFFF,    0x200000  ],
    "CACHE_LINE_SIZE" : [0xC,  1,  "RW",   0xFF,        0x0       ],
    "LATENCY_TIMER"   : [0xD,  1,  "RW",   0xFF,        0x0       ],
    "HEADER_TYPE"     : [0xE,  1,  "RW",   0xFF,        0x0       ],
    "BIST"            : [0xF,  1,  "RW",   0xFF,        0x0       ],
    "CSR_MEM_BASE"    : [0x10, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "CSR_IO_BASE"     : [0x14, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "FLASH_MEM_BASE"  : [0x18, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "SUB_VENDOR_ID"   : [0x2C, 2,  "RW",   0xFFFF,      0x0       ],
    "SUB_ID"          : [0x2E, 2,  "RW",   0xFFFF,      0x0       ],
    "EX_ROM_BASE"     : [0x30, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "CAP_PTR"         : [0x34, 1,  "RW",   0xFF,        0xDC      ],
    "INTERRUPT_LINE"  : [0x3C, 1,  "RW",   0xFF,        0x0       ],
    "INTERRUPT_PIN"   : [0x3D, 1,  "RW",   0xFF,        0x0       ],
    "MIN_GNT"         : [0x3E, 1,  "RW",   0xFF,        0x0       ],
    "MAX_GNT"         : [0x3F, 1,  "RW",   0xFF,        0x0       ],
    "CAP_ID"          : [0xDC, 1,  "RW",   0xFF,        0x0       ],
    "NEXT_ITEM_PTR"   : [0xDD, 1,  "RW",   0xFF,        0x0       ],
    "PM_CAP"          : [0xDE, 2,  "RW",   0xFFFF,      0x0       ],
    "PM_CSR"          : [0xE0, 2,  "RW",   0xFFFF,      0x0       ],
    "DATA"            : [0xE2, 1,  "RW",   0xFF,        0x0       ]
}

csr_registers = {
    #name             : [offset,    size,   r/w,   mask,   default value]
    "STATUS"          : [0x0,  2,  "RW",   0xFFFF,      0x0       ],
    "COMMAND"         : [0x2,  2,  "RW",   0xFFFF,      0x0       ],
    "GENERAL_PTR"     : [0x4,  4,  "RW",   0xFFFFFFFF,  0x0       ],
    "PORT"            : [0x8,  4,  "RW",   0xFFFFFFFF,  0x0       ],
    "EEPROM_CONTROL"  : [0xE,  2,  "RW",   0xFFFF,      0x0       ],
    "MDI_CONTROL"     : [0x10, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "RX_BYTE_COUNT"   : [0x14, 4,  "RW",   0xFFFFFFFF,  0x0       ],
    "FLOW_CONTROL"    : [0x19, 2,  "RW",   0xFFFF,      0x0       ],
    "PMDR"            : [0x1B, 1,  "RW",   0xFF,        0x0       ],
    "GENERAL_CONTROL" : [0x1C, 1,  "RW",   0xFF,        0x0       ],
    "GENERAL_STATUS"  : [0x1D, 1,  "RW",   0xFF,        0x0       ]
}

reg_attr_off = 0
reg_attr_size = 1
reg_attr_ops = 2
reg_attr_mask = 3
reg_attr_default = 4

#CU command opcode
cu_cmd_nop    = 0
cu_cmd_start  = 1
cu_cmd_resume = 2
cu_cmd_ldca   = 4  #Load Dump Counters Address
cu_cmd_dsc    = 5  #Dump Statistical Counters
cu_cmd_lcb    = 6  #Load CU Base
cu_cmd_drsc   = 7  #CU Dump and Reset Statistical Counters
cu_cmd_sr     = 10 #CU Static Resume

#RU command opcode
ru_cmd_nop    = 0
ru_cmd_start  = 1
ru_cmd_resume = 2
ru_cmd_rdr    = 3 #Receive DMA Redirect
ru_cmd_abt    = 4 #RU Abort
ru_cmd_lhds   = 5 #Load Header Data Size
ru_cmd_lrb    = 6 #Load RU Base

#Reset
software_reset  = 0x0000
selftest        = 0x0001
selective_reset = 0x0002

#Base addresses
cu_base = [main_memory_base, main_memory_base + 0x10000]
ru_base = [main_memory_base + 0x1000, main_memory_base + 0x11000]

phyaddr = [phy_address0, phy_address1]

csr_mem_base_set_flag   = [False, False]
csr_io_base_set_flag    = [False, False]
ex_mem_base_set_flag    = [False, False]
flash_mem_base_set_flag = [False, False]

#Transmit Mode
SimpleModeTx   = 0
FlexibleModeTx = 1
ShortTx        = 2

#CU command buffers
cu_num_max = 25
cu_action = [ None for i in range(cu_num_max)]

#RU RFD buffers
rfd_num_max = 25
rx_buf = [None for i in range(rfd_num_max)]

#time expire define
expire_max_cycle = 1000000


scb_command = dev_util.Bitfield_LE({
                        "RUC"   : (0,   2),
                        "CUC"   : (4,  7),
                        "MASK"  : (8),
                        "SI"    : (9),
                        "SIM"   : (10,  15)
                })
class regs_def:
    def __init__(self, mem_obj, mem_if, id):
        self.mem_obj = mem_obj
        self.mem_if  = mem_if
        self.id      = id
        if self.id == 0 :
            self.pci_regs_base = nic_pci_config_base[0]
            self.csr_regs_base = nic_csr_base[0]
        else :
            self.pci_regs_base = nic_pci_config_base[1]
            self.csr_regs_base = nic_csr_base[1]

    def get_reg_addr(self, reg_name):
        if reg_name in pci_registers:
            return (self.pci_regs_base + pci_registers[reg_name][reg_attr_off])
        elif reg_name in csr_registers:
            if csr_mem_base_set_flag[self.id] == False :
                raise Exception("CSR memory base is not set")
            return (self.csr_regs_base + csr_registers[reg_name][reg_attr_off])
        else:
            raise Exception("Unknown register:%s"%reg_name)

    def get_reg_len(self, reg_name):
        if reg_name in pci_registers:
            return pci_registers[reg_name][reg_attr_size]
        elif reg_name in csr_registers:
            return csr_registers[reg_name][reg_attr_size]
        else:
            raise Exception("Unknown register:%s"%reg_name)

    def read_reg(self, reg_name):
        reg_addr = self.get_reg_addr(reg_name)
        reg_len = self.get_reg_len(reg_name)
 #       print "reg_addr: 0x%X, reg_len: %d"%(reg_addr, reg_len)
        reg_bytes = self.mem_if.read(None, reg_addr, reg_len, 0)
        reg_val = etc_util.bytes_to_value_le32(reg_bytes)
        return reg_val

    def write_reg(self, reg_name, reg_val):
        reg_addr = self.get_reg_addr(reg_name)
        reg_len = self.get_reg_len(reg_name)
        if reg_len == 1:
            reg_bytes = tuple(val & 0xFF)
        if reg_len == 2:
            reg_bytes = etc_util.value_to_bytes_le16(reg_val)
        elif reg_len == 4:
            reg_bytes = etc_util.value_to_bytes_le32(reg_val)
        elif reg_len == 8:
            reg_bytes = etc_util.value_to_bytes_le64(reg_val)
        else:
            raise Exception("Register length %d is not 4 or 8!"%reg_len)
  #      print "write_reg: reg_addr %X"% reg_addr
  #      print "reg_bytes:", reg_bytes
        exception = self.mem_if.write(None, reg_addr, reg_bytes, 0)
        return exception

ethreg = [None, None]
#ethernet card 0 regs
ethreg[0] = regs_def(mem_space, mem_space_if, 0)
#ethernet card 1 regs
ethreg[1] = regs_def(mem_space, mem_space_if, 1)

SK_M = 0x1
CS_M = 0x2
DI_M = 0x4
DO_M = 0x8
ALL_M = 0xF

class TestShell:
    def __init__(self):
        #send and receive data backup
        self.send_data_backup = []
        self.receive_data     = []

    def wait(self, cycles):
        simics.SIM_continue(cycles)

    def enable_irq(self, id):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        ethreg[id].write_reg("COMMAND", intr_mask & ~(0x1 << 8))

    def disable_irq(self, id):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        ethreg[id].write_reg("COMMAND", intr_mask | 0x1 << 8)

    def initiate_eth(self, id):
        value = ethreg[id].read_reg("PCI_COMMAND")
        value = value | 0x6
        # Enable the master requesting for 82559
        ethreg[id].write_reg("PCI_COMMAND", value)
        # Map CSR memory base address
        ethreg[id].write_reg("CSR_MEM_BASE", nic_csr_base[id])
        csr_mem_base_set_flag[id]   = True
        # Map other base address

    def hw_reset(self, id):
        self.selective_reset(id)
        # Software reset
        ethreg[id].write_reg("PORT", software_reset)

    def selective_reset(self, id):
        ethreg[id].write_reg("PORT", selective_reset)

    def set_cu_base(self, id, base_addr):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        ethreg[id].write_reg("GENERAL_PTR", base_addr)
        new_cmd = intr_mask | scb_command.value(CUC=cu_cmd_lcb)
        ethreg[id].write_reg("COMMAND", new_cmd)

    def set_ru_base(self, id, base_addr):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        ethreg[id].write_reg("GENERAL_PTR", base_addr)
        new_cmd = intr_mask | scb_command.value(RUC=ru_cmd_lrb)
        ethreg[id].write_reg("COMMAND", new_cmd)

    def start_cu(self, id, cu_buf_addr):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        new_cmd = intr_mask | scb_command.value(CUC=cu_cmd_start)
        ethreg[id].write_reg("GENERAL_PTR", cu_buf_addr)
        ethreg[id].write_reg( "COMMAND", new_cmd)

    def resume_cu(self, id):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        new_cmd = intr_mask | scb_command.value(CUC=cu_cmd_resume)
        ethreg[id].write_reg( "COMMAND", new_cmd)

    def start_ru(self, id, ru_buf_addr):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        new_cmd = intr_mask | scb_command.value(RUC=ru_cmd_start)
        ethreg[id].write_reg("GENERAL_PTR", ru_buf_addr)
        ethreg[id].write_reg( "COMMAND", new_cmd)

    def resume_ru(self, id):
        intr_mask = ethreg[id].read_reg("COMMAND") & 0xFF00
        new_cmd = intr_mask | scb_command.value(RUC=ru_cmd_resume)
        ethreg[id].write_reg( "COMMAND", new_cmd)

    def wait_for_cmd_accepted(self, id):
        count = expire_max_cycle
        value = ethreg[id].read_reg( "COMMAND")
        while value & 0x00FF and count >= 10:
            self.wait(10)
            count -= 10
            value  = ethreg[id].read_reg( "COMMAND")
        if count < 10:
            raise Exception("Command is not accepted!")

    def wait_for_cuc_finished(self, id):
        count = expire_max_cycle
        value = ethreg[id].read_reg( "STATUS")
        while (value & 0x8000) == 0 and count >= 10:
            self.wait(1000)
            count -= 1000
            value  = ethreg[id].read_reg( "STATUS")
        if count < 10:
            raise Exception("CUC cannot be finished in %d cycles!" % expire_max_cycle)

    def enable_mdi_interrupt(self, id):
        value = ethreg[id].read_reg("MDI_CONTROL")
        ethreg[id].write_reg("MDI_CONTROL", value | (0x1 << 29))

    def disable_mdi_interrupt(self, id):
        value = ethreg[id].read_reg("MDI_CONTROL")
        ethreg[id].write_reg("MDI_CONTROL", value & ~(0x1 << 29))

    def wait_mdi_ready(self, id):
        count = expire_max_cycle
        value = ethreg[id].read_reg("MDI_CONTROL")
        is_ready = value & (0x1 << 28)
        while (is_ready == 0) and count >= 5:
            value = ethreg[id].read_reg("MDI_CONTROL")
            is_ready = value & (0x1 << 28)
            self.wait(5)
            count -= 5
        if count < 5:
            raise Exception("MDI is always busy!")

    def mdi_read(self, id, addr):
        value  = ethreg[id].read_reg("MDI_CONTROL")
        value  = value & 0xE0000000
        value |= 0x8000000 #read opcode
        value |= (phyaddr[id] & 0x1F) << 21 #PHY address
        value |= (addr & 0x1F) << 16 #PHY register address
        ethreg[id].write_reg("MDI_CONTROL", value )
        self.wait_mdi_ready(id)
        value  = ethreg[id].read_reg("MDI_CONTROL")
        return value & 0xFFFF

    def mdi_write(self, id, addr, data):
        value  = ethreg[id].read_reg("MDI_CONTROL")
        value  = value & 0xE0000000
        value |= 0x8000000 #read opcode
        value |= (phyaddr[id] & 0x1F) << 21   #PHY address
        value |= (addr & 0x1F) << 16   #PHY register address
        value |= data & 0xFFFF
        ethreg[id].write_reg("MDI_CONTROL", value )
        self.wait_mdi_ready(id)

    def set_timing(self, id, value, cs, sk, di):
        if cs :
            value |= CS_M
        if sk :
            value |= SK_M
        if di :
            value |= DI_M
        ethreg[id].write_reg("EEPROM_CONTROL", value )
        self.wait(5)

    def read_timing(self, id, value):
        data = 0
        for i in range(16) :
            self.set_timing(id, value, 1, 1, 0)
            self.set_timing(id, value, 1, 0, 0)
            value  = ethreg[id].read_reg("EEPROM_CONTROL")
            data  |= ((value & DO_M) >> 3) << (15-i)
        return data


    def eeprom_read(self, id, addr):
        value  = ethreg[id].read_reg("EEPROM_CONTROL")
        value &= ~ALL_M
        #start
        self.set_timing(id, value, 1, 1, 0)
        self.set_timing(id, value, 1, 0, 1)
        self.set_timing(id, value, 1, 1, 1)
        #send read opcode 10
        self.set_timing(id, value, 1, 0, 1)
        self.set_timing(id, value, 1, 1, 1)
        self.set_timing(id, value, 1, 0, 0)
        self.set_timing(id, value, 1, 1, 0)
        #send addr 6 bits
        self.set_timing(id, value, 1, 0, addr & (0x1 << 5))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 5))
        self.set_timing(id, value, 1, 0, addr & (0x1 << 4))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 4))
        self.set_timing(id, value, 1, 0, addr & (0x1 << 3))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 3))
        self.set_timing(id, value, 1, 0, addr & (0x1 << 2))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 2))
        self.set_timing(id, value, 1, 0, addr & (0x1 << 1))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 1))
        self.set_timing(id, value, 1, 0, addr & (0x1 << 0))
        self.set_timing(id, value, 1, 1, addr & (0x1 << 0))
        self.set_timing(id, value, 1, 0, 0)
        #get read data
        data = self.read_timing(id, value)
        #de-assert CS
        self.set_timing(id, 0, 0, 1, 0 )
        self.set_timing(id, 0, 0, 0, 0 )
        self.set_timing(id, 0, 0, 1, 0 )
        self.set_timing(id, 0, 0, 0, 0 )
        self.set_timing(id, 0, 0, 1, 0 )
        self.set_timing(id, 0, 0, 0, 0 )
        self.set_timing(id, 0, 0, 1, 0 )
        self.set_timing(id, 0, 0, 0, 0 )
        ethreg[id].write_reg("EEPROM_CONTROL", 0 )
        self.wait(50)
        return data

    def eeprom_read_test(self, id) :
        self.eeprom_read(0, 0x2)
        self.eeprom_read(0, 0x1)
        self.eeprom_read(0, 0x0)

    def update_cu_status(self, id, cu_buf_addr, cu_action, num):
        assert num <= cu_num_max
        next_addr = cu_buf_addr
        for i in range(num) :
            if cu_action[i] == None :
                break
            result = mem_read(cu_base[id] + next_addr, cu_action[i].len)
            cu_action[i].update_status_from_memory(result)
            next_addr = cu_action[i].get_link_addr()
            if next_addr == 0:
                break

    def check_cu_status(self, id, cu_action, num):
        assert num <= cu_num_max
        for i in range(num) :
            if cu_action[i] == None :
                break
            if cu_action[i].get_el() :
                break
            if cu_action[i].get_ok() :
                continue
            else :
                return False
        return True

    def update_ru_status(self, id, ru_buf_addr, rx_buf, num):
        assert num <= rfd_num_max
        next_addr = ru_buf_addr
        for i in range(num) :
            if rx_buf[i] == None :
                break
 #           print "Read RFD from address: ", (ru_base[id] + next_addr)
            result = mem_read(ru_base[id] + next_addr, rx_buf[i].size)
            rx_buf[i].update_status_from_memory(result)
            next_addr = rx_buf[i].get_link_addr()
            if next_addr == 0 :
                break

    def check_ru_complete(self, id, rx_buf, num):
        assert num <= rfd_num_max
        for i in range(num) :
            if rx_buf[i] == None :
                break
            if rx_buf[i].get_eof():
                return True
        return False

    def check_ru_status(self, id, rx_buf, num):
        assert num <= rfd_num_max
        for i in range(num) :
            if rx_buf[i] == None :
                break
            if rx_buf[i].get_eof():
                if rx_buf[i].get_ok() :
                    self.receive_data += rx_buf[i].ru_buf[16:rx_buf[i].actual_count+16]
                    continue
                else :
                    return False
            elif i == 0:
                return False
            else :
                break
        return True

    def set_ia(self, id, addr):
        #Prepare memory for command block of CU
        cu_action[0] = cu_ia()
        cu_action[0].set_ia(tuple(addr))
        cu_buf_addr = 0x0000
        mem_write(cu_base[id] + cu_buf_addr, tuple(cu_action[0].cu_buf))
        self.start_cu(id, cu_buf_addr)
        self.wait(10)
        self.wait_for_cmd_accepted(id)
        self.update_cu_status(id, cu_buf_addr, cu_action, 1)
        if self.check_cu_status(id, cu_action, 1) :
          #  print "Set Individual Address ok."
            pass
        else :
            raise Exception( "Set Individual Address failed!")

    def self_test(self, id):
        dma_addr  = main_memory_base
        result    = etc_util.value_to_bytes_le32(0xFFFFFFFF)
        signature = [0, 0, 0, 0]
        mem_write(dma_addr, signature)
        mem_write(dma_addr + 4, result)
        ethreg[id].write_reg("PORT", dma_addr | selftest)
        self.wait_for_cmd_accepted(id)
        signature = mem_read(dma_addr, 4)
        result    = mem_read(dma_addr + 4, 4)
        if signature == (0, 0, 0, 0) or result != (0, 0, 0, 0) :
            print("signature = ",signature)
            print("result = ", result)
            raise Exception("Self test failed!")
        else :
          #  print "Self test pass."
            pass

    def clear_data_backup(self) :
        self.send_data_backup = []
        self.receive_data = []

    def tx_test(self, id, mode):
        #Prepare memory for command block of CU
        ethreg[0].write_reg("STATUS", 0x8000)
        cu_action = [ None for i in range(cu_num_max)]
        cu_buf_addr = [0x0, 0x100]
        cu_action[0] = cu_tx()
        cu_action[0].set_i()
        cu_action[1] = cu_nop()
        cu_action[1].set_el()
        cu_action[0].set_link_addr_val(cu_buf_addr[1])
 #       cu_action[0].set_nc() #let the device add CRC and Source Address
        if mode == ShortTx :
            cu_action[0].set_tbd_addr_val(0xffffffff)
            cu_action[0].set_tcb_count_val(20)
            cu_action[0].add_payload(eth_frame_short)
            self.send_data_backup += eth_frame_short_pad
            cu_action[0].set_tbd_eof()
        elif mode == SimpleModeTx :
            cu_action[0].set_tbd_addr_val(0xffffffff)
            cu_action[0].set_tcb_count_val(64)
            cu_action[0].add_payload(eth_frame)
            self.send_data_backup += eth_frame
            cu_action[0].set_tbd_eof()
        else :
            frame_addrs = [0x200, 0x400]
            tbd_base    = 0x600
            tbd = tbd_table()
            tbd.add_tbd(cu_base[id] + frame_addrs[0], 64, 0)
            tbd.add_tbd(cu_base[id] + frame_addrs[1], 64, 1)
            cu_action[0].set_tbd_addr_val(tbd_base)
            cu_action[0].set_sf()
            cu_action[0].set_tbd_num_val(2)  #set TBD number
            mem_write(cu_base[id] + tbd_base, tuple(tbd.tbd))
            mem_write(cu_base[id] + frame_addrs[0], tuple(eth_frame))
            mem_write(cu_base[id] + frame_addrs[1], tuple(eth_frame))
            self.send_data_backup += eth_frame
            self.send_data_backup += eth_frame
        mem_write(cu_base[id] + cu_buf_addr[0], tuple(cu_action[0].cu_buf))
        mem_write(cu_base[id] + cu_buf_addr[1], tuple(cu_action[1].cu_buf))
        self.start_cu(id, cu_buf_addr[0])
        self.wait_for_cmd_accepted(id)
        self.wait_for_cuc_finished(id)
        self.update_cu_status(id, cu_buf_addr[0], cu_action, 2)
        if self.check_cu_status(id, cu_action, 2) :
            pass
        else :
            print(cu_action[0].cu_buf)
            print(cu_action[1].cu_buf)
            if mode == SimpleModeTx :
                raise Exception( "Simple mode transmit test failed!")
            elif mode == ShortTx :
                raise Exception( "Short packet transmit test failed!")
            else :
                raise Exception("Flexible mode transmit test failed!")

    def rx_wait(self, id):
        #Prepare memory for command block of CU
        rx_rfd_addrs  = [0, 0x600, 0xC00, 0x1200]
        rx_frame_size_max = 0x600
        rx_buf[0] = ru_rfd(rx_frame_size_max)
        rx_buf[1] = ru_rfd(rx_frame_size_max)
        rx_buf[2] = ru_rfd(rx_frame_size_max)
        rx_buf[3] = ru_rfd(rx_frame_size_max)
        rx_buf[0].set_link_addr_val(rx_rfd_addrs[1])
        rx_buf[1].set_link_addr_val(rx_rfd_addrs[1])
        rx_buf[2].set_link_addr_val(rx_rfd_addrs[1])
        rx_buf[3].set_link_addr_val(rx_rfd_addrs[1])
        rx_buf[3].set_el()
        mem_write(ru_base[id] + rx_rfd_addrs[0], tuple(rx_buf[0].ru_buf))
        mem_write(ru_base[id] + rx_rfd_addrs[1], tuple(rx_buf[1].ru_buf))
        mem_write(ru_base[id] + rx_rfd_addrs[2], tuple(rx_buf[2].ru_buf))
        mem_write(ru_base[id] + rx_rfd_addrs[3], tuple(rx_buf[3].ru_buf))
        self.start_ru(id, rx_rfd_addrs[0])
        self.wait_for_cmd_accepted(id)
        self.wait(10)

    def rx_check(self, id, check_crc):
        print("check id:", id)
        rx_rfd_addrs  = [0, 0x900]
        self.update_ru_status(id, rx_rfd_addrs[0], rx_buf, 2)
        while self.check_ru_complete(id, rx_buf, 2) == False :
            self.wait(50)
            self.update_ru_status(id, rx_rfd_addrs[0], rx_buf, 2)
        status = self.check_ru_status(id, rx_buf, 2)
        if status and self.send_data_backup == self.receive_data[0:-4]:
            if (check_crc == self.receive_data[-4:]):
                pass
            else :
                print("expected crc:")
                print(check_crc)
                print("receive crc is:")
                print(self.receive_data[-4:])
                raise Exception("Receive Frames test failed!")
        else :
            print("send data is:")
            print(self.send_data_backup)
            print("receive data is:")
            print(self.receive_data[0:-4])
            print("receive crc is:")
            print(self.receive_data[-4:])
            raise Exception("Receive Frames test failed!")

    def cfg_and_dump_test(self, id):
        cu_action = [ None for i in range(cu_num_max)]
        dump_addr    = 0x300
        cu_buf_addr  = [0, 0]
        cu_action[0] = cu_cfg()
        cu_action[0].set_parameters(cfg_para)
        mem_write(cu_base[id] + cu_buf_addr[0], tuple(cu_action[0].cu_buf))
        self.start_cu(id, cu_buf_addr[0])
        self.wait_for_cmd_accepted(id)
        self.wait(10)
        cu_action[1] = cu_dump()
        cu_action[1].set_dump_addr(dump_addr)
        mem_write(cu_base[id] + cu_buf_addr[1], tuple(cu_action[1].cu_buf))
        self.start_cu(id, cu_buf_addr[1])
        self.wait_for_cmd_accepted(id)
        self.wait(10)
        dump_data = mem_read(cu_base[id] + dump_addr, 596)
        dump_data = list(dump_data)
        if dump_data[24:38] == cfg_para[8:22]:
        #    print "Configure and Dump test pass."
            pass
        else :
            print("Dump configure data")
            print(dump_data[24:38])
            print("Compare configure data")
            print(cfg_para[8:22])
            raise Exception("Configure and Dump test failed!")

    def check_and_clear_interrupt(self, id):
        intr_mask   = ethreg[id].read_reg("COMMAND") & 0xFF00
        intr_status = ethreg[id].read_reg("STATUS") & 0xFF00
        if intr_mask & (0x1 << 8) : #All interrupts are masked
         #   print "All interrupts are masked."
            return
        if (((~intr_mask) & intr_status) & 0xF000 == 0
            and ((((~intr_mask) & 0x0400) >> 2) & intr_status) == 0 \
            and (intr_status & 0xF600) == 0) :  # No unmasked interrupt suspend
         #   print "Interrupt are cleared."
            return
        test_state.seq = []
        ethreg[id].write_reg("STATUS", intr_status & ((~intr_mask) & 0xFF00))
        intr_status1 = ethreg[id].read_reg("STATUS") & 0xFF00
        if intr_status1 & (intr_status & (~intr_mask)) :
            print("Interrupt Mask: ", intr_mask)
            print("Status: ", intr_status)
            raise Exception("Clear interrupt failed!")
        elif test_state.seq[len(test_state.seq) - 1][0] != 'clear' :
            print("Interrupt Mask: ", intr_mask)
            print("Status: ", intr_status)
            raise Exception("Clear interrupt failed, the interrupt pin should be lowered.")
        else :
          #  print "Clear interrupt ok."
            pass

    def sw_set_interrupt_test(self, id):
        test_state.seq = []
        intr_mask   = ethreg[id].read_reg("COMMAND") & 0xFF00
        ethreg[id].write_reg("COMMAND", intr_mask | (0x1 << 9))
        intr_status = ethreg[id].read_reg("STATUS") & 0xFF00
        if (intr_status & (0x1 << 10)
            and test_state.seq[len(test_state.seq) - 1][0] == 'raise') :
         #   print "Software set interrupt test pass."
            pass
        else :
            print("Interrupt Mask: ", intr_mask)
            print("Status: ", intr_status)
            print("Test state: ")
            print(test_state.seq)
            raise Exception("Software set interrupt test failed!")

    def cu_resume_test(self, id):
        cu_action = [ None for i in range(cu_num_max)]
        test_state.seq = []
        cu_buf_addr  = [0, 0x100, 0x200, 0x300]
        cu_action[0] = cu_cfg()
        cu_action[0].set_parameters(cfg_para)
        cu_action[0].set_link_addr_val(cu_buf_addr[1])
        cu_action[0].set_i()
        cu_action[1] = cu_nop()
        cu_action[1].set_link_addr_val(cu_buf_addr[2])
        cu_action[1].set_i()
        cu_action[2] = cu_nop()
        cu_action[2].set_link_addr_val(cu_buf_addr[3])
        cu_action[2].set_s()
        cu_action[3] = cu_nop()
        cu_action[3].set_link_addr_val(cu_buf_addr[2])
      #  cu_action[3].set_el()
        mem_write(cu_base[id] + cu_buf_addr[0], tuple(cu_action[0].cu_buf))
        mem_write(cu_base[id] + cu_buf_addr[1], tuple(cu_action[1].cu_buf))
        mem_write(cu_base[id] + cu_buf_addr[2], tuple(cu_action[2].cu_buf))
        mem_write(cu_base[id] + cu_buf_addr[3], tuple(cu_action[3].cu_buf))
        self.start_cu(id, cu_buf_addr[0])
        self.wait_for_cmd_accepted(id)
        self.wait_for_cuc_finished(id)
        #self.wait(100000000)
        self.check_and_clear_interrupt(id)
        cu_action[2].clear_c()
        cu_action[1].clear_c()
        mem_write(cu_base[id] + cu_buf_addr[2], tuple(cu_action[2].cu_buf))
        mem_write(cu_base[id] + cu_buf_addr[1], tuple(cu_action[1].cu_buf))
        self.resume_cu(id)
        self.wait_for_cmd_accepted(id)
        #self.wait_for_cuc_finished(id)
        self.wait(1000)
        self.check_and_clear_interrupt(id)
