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


# usb_tb.py
# testbench of USB UHCI/EHCI controllers in ICH9

import pyobj
import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))
import pcibus

ich9_uhci_cnt           = 6
ich9_ehci_cnt           = 2

# Main memory and its division
ich9_main_mem_size      = 0x10000000 # 256M
ich9_main_mem_base      = 0x80000000 # Upper 2GB
ehci_que_addr           = ich9_main_mem_base + 0x00000
ehci_qtd_addr           = ehci_que_addr      + 0x10000
ehci_setup_addr         = ehci_qtd_addr      + 0x10000
ehci_ibuf_addr          = ehci_setup_addr    + 0x10000
ehci_obuf_addr          = ehci_ibuf_addr     + 0x40000

uhci_area_base          = ich9_main_mem_base + 0x100000
uhci_que_addr           = uhci_area_base     + 0x00000
uhci_td_addr            = uhci_que_addr      + 0x10000
uhci_setup_addr         = uhci_td_addr       + 0x10000
uhci_ibuf_addr          = uhci_setup_addr    + 0x10000
uhci_obuf_addr          = uhci_ibuf_addr     + 0x40000
uhci_frame_list_addr    = uhci_area_base     + 0xF0000

test_usb_dev_addr       = 8

bus_clk_freq_mhz        = 133

ich9_uhci_dev_num   = [29, 29, 29, 26, 26, 26]
ich9_uhci_func_num  = [0, 1, 2, 0, 1, 2]
ich9_uhci_reg_addr  = [
                          0x1000,
                          0x1100,
                          0x1200,
                          0x1300,
                          0x1400,
                          0x1500,
                      ]

ich9_ehci_dev_num = [29, 26]
ich9_ehci_func_num = [7, 7]
ich9_ehci_reg_addr = [
                      0x2000,
                      0x2100,
                    ]

ich9_uhci_io_base = [
                        0x3000,
                        0x3100,
                        0x3200,
                        0x3300,
                        0x3400,
                        0x3500,
                    ]
ich9_ehci_io_base = [
                        0x4000,
                        0x4800, # falls above bit 9
                    ]

class UsbConst:
    # Four transfer types
    type_control        = 0
    type_interrupt      = 1
    type_isochronous    = 2
    type_bulk           = 3

    # Three PID types
    pid_in              = 0x69
    pid_out             = 0xE1
    pid_setup           = 0x2D

    # Request code
    req_set_address     = 5

    max_pkt_size        = 512

    ehci_qtd_len        = 32
    ehci_qtd_len64      = 52
    ehci_qh_len         = 48
    ehci_qh_len64       = 68
    ehci_qtd_pid_out    = 0
    ehci_qtd_pid_in     = 1
    ehci_qtd_pid_setup  = 2

    ehci_bf_qh_dw1 = dev_util.Bitfield_LE({
                        "DA"    : (6, 0), # Device Address
                        "I"     : (7),
                        "END_PT": (11, 8),
                        "EPS"   : (13, 12),
                        "DTC"   : (14),
                        "H"     : (15),
                        "MPL"   : (26, 16), # Maximum Packet Length
                        "C"     : (27),
                        "RL"    : (31, 28)
                    })

    ehci_bf_qh_dw2 = dev_util.Bitfield_LE({
                        "SMASK" : (7, 0),
                        "CMASK" : (15, 8),
                        "HA"    : (22, 16), # Hub Address
                        "PN"    : (29, 23),
                        "MULT"  : (31, 30)
                    })

    ehci_bf_qtd_dw2 = dev_util.Bitfield_LE({
                        "STS"   : (7, 0),
                        "PID"   : (9, 8),
                        "CERR"  : (11, 10),
                        "CPAGE" : (14, 12),
                        "IOC"   : (15),
                        "TB"    : (30, 16),
                        "DT"    : (31)
                    })

    uhci_td_len = 32
    uhci_qh_len = 8

    uhci_bf_td_dw0 = dev_util.Bitfield_LE({
                        "T"         : (0),
                        "Q"         : (1),
                        "VF"        : (2),
                        "LP"        : (31, 4)
                    })

    uhci_bf_td_dw1 = dev_util.Bitfield_LE({
                        "ACTLEN"    : (10, 0),
                        "STATUS"    : (23, 16),
                        "IOC"       : (24),
                        "IOS"       : (25),
                        "LS"        : (26),
                        "CERR"      : (28, 27),
                        "SPD"       : (29),
                    })

    uhci_bf_td_dw2 = dev_util.Bitfield_LE({
                        "PID"       : (7, 0),
                        "DEVADDR"   : (14, 8),
                        "ENDPT"     : (18, 15),
                        "D"         : (19),
                        "MAXLEN"    : (31, 21),
                    })

    uhci_bf_qh_dw0 = dev_util.Bitfield_LE({
                        "T"         : (0),
                        "Q"         : (1),
                        "QHLP"      : (31, 4),
                    })

    uhci_bf_qh_dw1 = dev_util.Bitfield_LE({
                        "T"         : (0),
                        "Q"         : (1),
                        "QELP"     : (31, 4),
                    })

    uhci_bf_frame = dev_util.Bitfield_LE({
                        "T"         : (0),
                        "Q"         : (1),
                        "FP"        : (31, 4),
                    })

class UhciConst:
    reset_val = {
                    "VID"   : 0x8086,
                    #"DID"   : 0x2934, # in ICH9
                    "DID"   : 0x3A64, # in ICH10
                    "CMD"   : 0x0000,
                    "STS"   : 0x0290,
                    "RID"   : 0x02,
                    "PI"    : 0x00,
                    "SCC"   : 0x03,
                    "BCC"   : 0x0C,
                    "BAR0"  : 0x00000000,
                    "BAR1"  : 0x00000000,
                    "BASE"  : 0x00000001,
                    "SVID"  : 0x0000,
                    "SID"   : 0x0000,
                    "CAPTR" : 0x50,
                    "INTLN" : 0x00,

                    # Capability registers
                    "FLRCID"    : 0x09,
                    "FLRNCP"    : 0x00,
                    "FLRCLV"    : 0x2006,
                    "USB_FLRCTRL":0x00,
                    "USB_FLRSTAT":0x00,
                    "USB_RELNUM": 0x10,
                    "USB_LEGKEY": 0x2000,
                    "USB_RES"   : 0x00,
                    "CWP"       : 0x00,
                    "UCR1"      : 0x00,

                    # USB I/O registers
                    "USBCMD"    : 0x0000,
                    "USBSTS"    : 0x0020,
                    "USBINTR"   : 0x0000,
                    "FRNUM"     : 0x0000,
                    "FRBASEADD" : 0x0000,
                    "SOFMOD"    : 0x40,
                    "PORTSC0"   : 0x0080,
                    "PORTSC1"   : 0x0080,
                }

class EhciConst:
    reset_val = {
                    "VID"   : 0x8086,
                    #"DID"   : 0x293A, # in ICH9
                    "DID"   : 0x3A6A, # in ICH10
                    "CMD"   : 0x0000,
                    "STS"   : 0x0290,
                    "RID"   : 0x02,
                    "PI"    : 0x20,
                    "SCC"   : 0x03,
                    "BCC"   : 0x0C,
                    "PMLT"  : 0x00,
                    "BAR0"  : 0x00000000,
                    "SVID"  : 0x0000,
                    "SID"   : 0x0000,
                    "CAPTR" : 0x50,
                    "INTLN" : 0x00,

                    # Capability registers
                    "PWR_CAPID" : 0x01,
                    "NXT_PTR1"  : 0x58,
                    "PWR_CAP"   : 0xC9C2,
                    "PWR_CNTL_STS"  : 0x0000,
                    "DEBUG_CAPID"   : 0x0A,
                    "NXT_PTR2"  : 0x98,
                    "DEBUG_BASE": 0x20A0,
                    "USB_RELNUM": 0x20,
                    "FL_ADJ"    : 0x20,
                    "PWAKE_CAP" : 0x01FF,
                    "LEG_EXT_CAP"   : 0x00000001,
                    "LEG_EXT_CS"    : 0x00000000,
                    "SPECIAL_SMI"   : 0x00000000,
                    "ACCESS_CNTL"   : 0x00,
                    "EHCIIR1"       : 0x01,
                    "FLRCID"    : 0x09,
                    "FLRNCP"    : 0x00,
                    "FLRCLV"    : 0x2006,
                    "FLRCTRL"   : 0x00,
                    "FLRSTAT"   : 0x00,
                    "EHCIIR2"   : 0x20001706,

                    # USB I/O registers
                    "CAPLENGTH"     : 0x20,
                    "HCIVERSION"    : 0x0100,
                    "HCSPARAMS"    : 0x00103206,
                    "HCCPARAMS"     : 0x00006871,
                    "USB2.0_CMD"    : 0x00080000,
                    "USB2.0_STS"    : 0x00001000,
                    "USB2.0_INTR"   : 0x00000000,
                    "FRINDEX"       : 0x00000000,
                    "CTRLDSSEGMENT" : 0x00000000,
                    "PERIODICLISTBASE"  : 0x00000000,
                    "ASYNCLISTADDR"     : 0x00000000,
                    "CONFIGFLAG"        : 0x00000000,
                    "PORT0SC"           : 0x00003000,
                    "PORT1SC"           : 0x00003000,
                    "PORT2SC"           : 0x00003000,
                    "PORT3SC"           : 0x00003000,
                    "PORT4SC"           : 0x00003000,
                    "PORT5SC"           : 0x00003000,
                    "PORT6SC"           : 0x00003000,
                    "PORT7SC"           : 0x00003000,
                }

class ConfRegs(pyobj.ConfObject):
    class cs_conf(pyobj.Port):
        class int_register(pyobj.Interface):
            def read(self, num):
                data = {0x3108:0x10004321, 0x3114:0x30000321}
                return data.get(num,0)

class TestBench:
    def __init__(self):
        # Bus clock
        clk = simics.pre_conf_object('bus_clk', 'clock')
        clk.freq_mhz = bus_clk_freq_mhz
        simics.SIM_add_configuration([clk], None)
        self.bus_clk = conf.bus_clk

        # Main memory and its image
        main_img = simics.pre_conf_object('main_img', 'image')
        main_img.size = ich9_main_mem_size
        main_ram = simics.pre_conf_object('main_ram', 'ram')
        main_ram.image = main_img
        simics.SIM_add_configuration([main_img, main_ram], None)
        self.main_image = conf.main_img
        self.main_ram = conf.main_ram

        # Memory-space
        self.mem = simics.pre_conf_object('mem', 'memory-space')
        simics.SIM_add_configuration([self.mem], None)
        self.mem = conf.mem
        self.mem_iface = self.mem.iface.memory_space
        self.io_space = simics.SIM_create_object('memory-space', 'io_space', [])
        self.conf_space = simics.SIM_create_object('memory-space',
                                                   'conf_space', [])

        self.mem.map = [
                         [ich9_main_mem_base, self.main_ram,
                                    0xff, 0, ich9_main_mem_size],
                       ]
        # Initialize memory
        self.memory = dev_util.Memory()

        # PCI bus
        self.pci = simics.SIM_create_object('PCIBus', 'pci',
                                            [['memory', self.mem],
                                             ['io', self.io_space],
                                             ['conf', self.conf_space]])

        # Interrupt controller
        self.intc_py = dev_util.Dev([dev_util.SimpleInterrupt])
        self.intc = self.intc_py.obj

        # Chipset Config registers
        self.lpc = simics.SIM_create_object('ConfRegs', 'lpc', [])

        # Six UHCI controllers
        self.uhci = []
        for i in range(ich9_uhci_cnt):
            uhci = simics.pre_conf_object('uhci%d' % i, 'ich10_usb_uhci')
            uhci.pci_bus = self.pci
            uhci.queue   = self.bus_clk
            uhci.chipset_config = [self.lpc, 'cs_conf']
            uhci.pci_dev_num = ich9_uhci_dev_num[i]
            uhci.pcidev_func_num = ich9_uhci_func_num[i]
            uhci.pci_config_bus_address = ich9_uhci_dev_num[i] + ich9_uhci_func_num[i] + i
            simics.SIM_add_configuration([uhci], None)
            self.uhci.append(simics.SIM_get_object("uhci%d" % i))

            self.mem.map += [
                              [ich9_uhci_reg_addr[i], [self.uhci[i], 'pci_config'], 0xff, 0, 0x100],
                        ]

        # Two EHCI controllers
        self.ehci = []
        for i in range(ich9_ehci_cnt):
            ehci = simics.pre_conf_object('ehci%d' % i, 'ich10_usb_ehci')
            ehci.pci_bus = self.pci
            ehci.queue   = self.bus_clk
            ehci.chipset_config = [self.lpc, 'cs_conf']
            ehci.pci_dev_num = ich9_ehci_dev_num[i]
            ehci.pcidev_func_num = ich9_ehci_func_num[i]
            ehci.pci_config_bus_address = ich9_ehci_dev_num[i] + ich9_ehci_func_num[i] + i
            simics.SIM_add_configuration([ehci], None)
            self.ehci.append(simics.SIM_get_object("ehci%d" % i))

            self.mem.map += [
                              [ich9_ehci_reg_addr[i], [self.ehci[i], 'pci_config'], 0xff, 0, 0x100],
                        ]

        # The pseudo testing usb device
        self.usb_dev = simics.SIM_create_object("ich10_test_usb_device", "usb_dev", [])

    # Memory operation methods
    def read_mem(self, addr, size):
        return self.mem_iface.read(None, addr, size, 0)

    def write_mem(self, addr, bytes):
        self.mem_iface.write(None, addr, bytes, 0)

    def read_value_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_mem(addr, bits // 8))

    def write_value_le(self, addr, bits, value):
        self.write_mem(addr, dev_util.value_to_tuple_le(value, bits // 8))

    # IO space operation methods
    def read_io(self, addr, size):
        return self.io_space.iface.memory_space.read(None, addr, size, 0)

    def write_io(self, addr, bytes):
        self.io_space.iface.memory_space.write(None, addr, bytes, 0)

    def read_io_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_io(addr, bits // 8))

    def write_io_le(self, addr, bits, value):
        self.write_io(addr, dev_util.value_to_tuple_le(value, bits // 8))

    def map_hc_io(self, uhci_or_ehci, hc_idx):
        # Enable the io space mapping
        if uhci_or_ehci == "uhci":
            cmd_addr = ich9_uhci_reg_addr[hc_idx] + 0x4
            bar_addr = ich9_uhci_reg_addr[hc_idx] + 0x20
            mapped_addr = ich9_uhci_io_base[hc_idx]
        elif uhci_or_ehci == "ehci":
            cmd_addr = ich9_ehci_reg_addr[hc_idx] + 0x4
            bar_addr = ich9_ehci_reg_addr[hc_idx] + 0x20
            mapped_addr = ich9_ehci_io_base[hc_idx]
        else:
            assert 0
        reg_val = self.read_value_le(cmd_addr, 16)
        reg_val = reg_val | 0x1
        self.write_value_le(cmd_addr, 16, reg_val)
        self.write_value_le(bar_addr, 32, mapped_addr)

    def map_hc_mem(self, uhci_or_ehci, hc_idx):
        # Enable the io space mapping
        if uhci_or_ehci == "uhci":
            cmd_addr = ich9_uhci_reg_addr[hc_idx] + 0x4
            bar_addr = ich9_uhci_reg_addr[hc_idx] + 0x10
            mapped_addr = ich9_uhci_io_base[hc_idx]
        elif uhci_or_ehci == "ehci":
            cmd_addr = ich9_ehci_reg_addr[hc_idx] + 0x4
            bar_addr = ich9_ehci_reg_addr[hc_idx] + 0x10
            mapped_addr = ich9_ehci_io_base[hc_idx]
        else:
            assert 0
        reg_val = self.read_value_le(cmd_addr, 16)
        reg_val = reg_val | 0x2
        self.write_value_le(cmd_addr, 16, reg_val)
        self.write_value_le(bar_addr, 32, mapped_addr)

    def enable_pci_master(self, ehci_or_uhci, hc_idx, to_enable):
        reg_addr = ich9_uhci_reg_addr[hc_idx] + 0x4
        if ehci_or_uhci == "ehci":
            reg_addr = ich9_ehci_reg_addr[hc_idx] + 0x4
        reg_val = self.read_value_le(reg_addr, 16)
        if to_enable:
            reg_val = reg_val | 0x4
        else:
            reg_val = reg_val & ~0x4
        self.write_value_le(reg_addr, 16, reg_val)

    # Construct a control transfer descriptor to set the address of the usb device
    def construct_ehci_setup_qtd(self, this_addr, next_addr, setup_addr, dev_addr):
        qtd = [0x00] * UsbConst.ehci_qtd_len64
        qtd[0:4] = dev_util.value_to_tuple_le(next_addr, 4)
        qtd_dw2 = UsbConst.ehci_bf_qtd_dw2.value(STS = 1 << 7,
                        PID = UsbConst.ehci_qtd_pid_setup, CERR = 0, CPAGE = 0,
                        IOC = 0, TB = 8, DT = 0)
        qtd[8:12] = dev_util.value_to_tuple_le(qtd_dw2, 4)
        setup_frame = [0x00] * 8
        setup_frame[0] = 0x00
        setup_frame[1] = UsbConst.req_set_address
        setup_frame[2:4] = dev_util.value_to_tuple_le(dev_addr, 2)
        self.write_mem(setup_addr, tuple(setup_frame))
        qtd[12:14] = dev_util.value_to_tuple_le(setup_addr, 4)
        self.write_mem(this_addr, tuple(qtd))

    # Construct a bulk in/out transfer qTD
    def construct_ehci_bulk_qtd(self, this_addr, next_addr, pid, data_addr, data_len):
        qtd = [0x00] * UsbConst.ehci_qtd_len64
        qtd[0:4] = dev_util.value_to_tuple_le(next_addr, 4)
        qtd_dw2 = UsbConst.ehci_bf_qtd_dw2.value(STS = 1 << 7,
                        PID = pid, CERR = 0, CPAGE = 0,
                        IOC = 0, TB = data_len, DT = 0)
        qtd[8:12] = dev_util.value_to_tuple_le(qtd_dw2, 4)
        qtd[12:14] = dev_util.value_to_tuple_le(data_addr, 4)
        self.write_mem(this_addr, tuple(qtd))

    def construct_ehci_qh(self, qh_addr, next_qh, dev_addr, ep_num, cur_qtd, next_qtd):
        qh = [0x00] * 20
        qh[0:4] = dev_util.value_to_tuple_le(next_qh, 4)
        dw1_val = UsbConst.ehci_bf_qh_dw1.value(DA = dev_addr,
                        I = 0, END_PT = ep_num, EPS = 0, DTC = 0, H = 0,
                        MPL = UsbConst.max_pkt_size, C = 0, RL = 0)
        qh[4:8] = dev_util.value_to_tuple_le(dw1_val, 4)
        dw2_val = UsbConst.ehci_bf_qh_dw2.value(SMASK = 0,
                            CMASK = 0, HA = 0, PN = 0, MULT = 0)
        qh[8:12] = dev_util.value_to_tuple_le(dw2_val, 4)
        qh[12:16] = dev_util.value_to_tuple_le(cur_qtd, 4)
        qh[16:20] = dev_util.value_to_tuple_le(next_qtd, 4)
        self.write_mem(qh_addr, tuple(qh))

    # Construct a bulk in/out transfer TD for UHCI controllers
    def construct_uhci_td(self, this_addr, is_last_td, next_addr, pid,
                               dev_addr, ep_num, is_low_speed, data_addr, data_len):
        td = [0x00] * UsbConst.uhci_td_len
        td_dw0 = UsbConst.uhci_bf_td_dw0.value(
                        T = is_last_td, # T - Terminate
                        Q = 0, # Q: 0 = TD, 1 = QH
                        VF = 1, # Vf: 1 = Depth first, 0 = Breadth first
                        LP = next_addr >> 4
                        )
        td[0:4] = dev_util.value_to_tuple_le(td_dw0, 4)
        td_dw1 = UsbConst.uhci_bf_td_dw1.value(
                        ACTLEN = 0, # Actual Length, written by the host controller
                        STATUS = 1 << 7, # Active = 1 to enable the execution of this TD
                        IOC = 0, # IOC - Interrupt on Complete, 1 = Issue IOC
                        IOS = 0, # IOS - Isochronous Select, 1 = Isochronous TD, 0 = Non-isochronous TD
                        LS = is_low_speed, # LS - Low Speed Device, 1 = Low Speed Device, 0 = Full Speed Device
                        CERR = 0, # CERR - count of error, 00 = No Error Limit
                        SPD = 0 # SPD - Short Packet Detect, 0 = Disable
                    )
        td[4:8] = dev_util.value_to_tuple_le(td_dw1, 4)
        td_dw2 = UsbConst.uhci_bf_td_dw2.value(
                        PID = pid, # PID - Packet Identification
                        DEVADDR = dev_addr, # Device address
                        ENDPT = ep_num, # Endpoint number
                        D = 0,  # D - Data Toggle, used to synchronize between the endpoint and the host
                        MAXLEN = data_len - 1 # Maximum Length - the length to transfer
                    )
        td[8:12] = dev_util.value_to_tuple_le(td_dw2, 4)
        td[12:16] = dev_util.value_to_tuple_le(data_addr, 4)
        self.write_mem(this_addr, tuple(td))

    # Construct a UHCI transfer descriptor to set the address of the usb device
    def construct_uhci_setup_td(self, this_addr, setup_addr, dev_addr, is_low_speed):
        next_addr = upper_align_to_power2(this_addr + UsbConst.uhci_td_len, 4)
        setup_frame = [0x00] * 8
        setup_frame[0] = 0x00
        setup_frame[1] = UsbConst.req_set_address
        setup_frame[2:4] = dev_util.value_to_tuple_le(dev_addr, 2)
        self.write_mem(setup_addr, tuple(setup_frame))
        self.construct_uhci_td(this_addr, 0, next_addr, UsbConst.pid_setup,
                               0, 0, is_low_speed, setup_addr, 8)
        # Construct the status transfer TD
        tb.construct_uhci_td(next_addr, 1, 0, UsbConst.pid_setup,
                             0, 0, is_low_speed, setup_addr, 0x800)

    # Construct a queue header for UHCI controllers
    def construct_uhci_qh(self, qh_addr, next_qh, linked_td, is_last):
        qh = [0x00] * UsbConst.uhci_qh_len
        dw0_val = UsbConst.uhci_bf_qh_dw0.value(T = is_last, Q = 0, QHLP = next_qh >> 4)
        qh[0:4] = dev_util.value_to_tuple_le(dw0_val, 4)
        dw1_val = UsbConst.uhci_bf_qh_dw1.value(T = 0, Q = 0, QELP = linked_td >> 4)
        qh[4:8] = dev_util.value_to_tuple_le(dw1_val, 4)
        self.write_mem(qh_addr, tuple(qh))

    def construct_uhci_frame_list(self, list_addr, frame_cnt, *frame_val):
        frame_list = [0x00] * frame_cnt * 4
        byte_idx = 0
        for i in range(frame_cnt):
            frame_list[byte_idx: byte_idx + 4] = dev_util.value_to_tuple_le(frame_val[i], 4)
            byte_idx = byte_idx + 4
        self.write_mem(list_addr, tuple(frame_list))

tb = TestBench()

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))

def expect(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%d', expected '%d'" % (info, actual, expected))

def upper_align_to_power2(value, index):
    return (value + (1 << index) - 1) & ~((1 << index) - 1)
