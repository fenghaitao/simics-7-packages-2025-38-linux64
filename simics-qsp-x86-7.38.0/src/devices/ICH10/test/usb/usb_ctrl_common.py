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


# usb_ctrl_common.py,
# common usb controller definitions used by several subtests.

from simics import *
import conf
import sys, os
sys.path.append(os.path.join("..", "common"))
import pyobj
import dev_util as du
import pcibus
import stest

# SIMICS-21543
conf.sim.deprecation_level = 0

# USB standard constants
usb_max_pkt_size    = 512

usb_type_control    = 0
usb_type_interrupt  = 1
usb_type_isochronous= 2
usb_type_bulk       = 3

usb_dir_none        = 0
usb_dir_in          = 1
usb_dir_out         = 2

usb_speed_low       = 0
usb_speed_full      = 1
usb_speed_high      = 2

########
#
# Device specific parameters
#

freq_mhz            = 1024
enough_cycles       = 2000000 # 2ms

main_mem_size      = 0x10000000 # 256M
main_mem_base      = 0x80000000 # Upper 2GB

ehci_que_addr      = main_mem_base + 0x00000
ehci_qtd_addr      = ehci_que_addr + 0x10000
ehci_setup_addr    = ehci_qtd_addr + 0x10000
ehci_ibuf_addr     = ehci_setup_addr + 0x10000
ehci_obuf_addr     = ehci_ibuf_addr + 0x40000

# EHCI controller parameters
n_ehci = 2
ehci_dev_num = [29, 26]
ehci_func_num = [7, 7]
ehci_reg_addr = [
    0x2000,
    0x2100,
    ]
ehci_io_base = [
    0x4000,
    0x4800, # falls above bit 9
    ]
ehci_log_level = 4

# UHCI controller parameters
n_uhci = 6
uhci_dev_num   = [29, 29, 29, 26, 26, 26]
uhci_func_num  = [0, 1, 2, 0, 1, 2]
uhci_reg_addr  = [
    0x1000,
    0x1100,
    0x1200,
    0x1300,
    0x1400,
    0x1500,
    ]
uhci_log_level = 4

# Create a clock to queue the events of ethernet-link
clk = pre_conf_object('clk', 'clock')
clk.freq_mhz = freq_mhz
SIM_add_configuration([clk], None)
clk = conf.clk

######################
#
# Chipset Config registers
class ConfRegs(pyobj.ConfObject):
    class cs_conf(pyobj.Port):
        class int_register(pyobj.Interface):
            def read(self, num):
                data = {0x3108:0x10004321, 0x3114:0x30000321}
                return data.get(num,0)
lpc = SIM_create_object('ConfRegs', 'lpc', [])
#
# Memory-space
#
mem = pre_conf_object('mem', 'memory-space')
SIM_add_configuration([mem], None)
mem = conf.mem
mem_iface = mem.iface.memory_space
io_space = SIM_create_object('memory-space', 'io_space', [])
conf_space = SIM_create_object('memory-space',
                               'conf_space', [])
du_mem = du.Memory()
mem.map += [
    [ehci_que_addr, du_mem.obj,
     0, ehci_que_addr, 0x10000],
    [ehci_qtd_addr, du_mem.obj,
     0, ehci_qtd_addr, 0x10000],
    [ehci_setup_addr, du_mem.obj,
     0, ehci_setup_addr, 0x10000],
    [ehci_ibuf_addr, du_mem.obj,
     0, ehci_ibuf_addr, 0x30000],
    [ehci_obuf_addr, du_mem.obj,
     0, ehci_obuf_addr, 0x30000],
    ]

# PCI
pcibus = SIM_create_object('PCIBus', 'pci',
                           [['memory', mem],
                            ['io', io_space],
                            ['conf', conf_space]])

# Create the EHCI host controllers
ehci_list = [None]*n_ehci
#
for i in range(n_ehci):
    ehci = pre_conf_object('ehci%d' % i, 'ich10_usb_ehci')
    ehci.log_level = ehci_log_level
    ehci.queue = clk
    ehci.pci_bus = pcibus
    ehci.chipset_config = [lpc, 'cs_conf']
    ehci.pci_dev_num = ehci_dev_num[i]
    ehci.pcidev_func_num = ehci_func_num[i]
    ehci.pci_config_bus_address = ehci_dev_num[i] + ehci_func_num[i] + i
    SIM_add_configuration([ehci], None)
    ehci_list[i] = getattr(conf, "ehci%d" % i)
    conf_space.map += [
        [ehci_reg_addr[i], [ehci_list[i], 'pci_config'], 0xff, 0, 0x100],
        ]

# Create the UHCI host controllers
uhci_list = [None]*n_uhci
#
for i in range(n_uhci):
    uhci = pre_conf_object('uhci%d' % i, 'ich10_usb_uhci')
    uhci.log_level = uhci_log_level
    uhci.queue = clk
    uhci.pci_bus = pcibus
    uhci.chipset_config = [lpc, 'cs_conf']
    uhci.pci_dev_num = uhci_dev_num[i]
    uhci.pcidev_func_num = uhci_func_num[i]
    uhci.pci_config_bus_address = uhci_dev_num[i] + uhci_func_num[i] + i
    SIM_add_configuration([uhci], None)
    uhci_list[i] = getattr(conf, "uhci%d" % i)
    conf_space.map += [
        [uhci_reg_addr[i], [uhci_list[i], 'pci_config'], 0xff, 0, 0x100],
        ]

# Set UHCI as companion host controllers
for i in range(n_ehci):
    idx = i * 3
    ehci_list[i].companion_hc = [uhci_list[idx], uhci_list[idx],
                            uhci_list[idx + 1], uhci_list[idx + 1],
                            uhci_list[idx + 2], uhci_list[idx + 2]]

########
#
# PCI config registers
#
ehci_pciconf_vid_reg = [None]*n_ehci
ehci_pciconf_did_reg = [None]*n_ehci
ehci_pciconf_cmd_reg = [None]*n_ehci
ehci_pciconf_memaddr_reg = [None]*n_ehci
ehci_pciconf_ioaddr_reg = [None]*n_ehci
ehci_pciconf_dbg_capid_reg = [None]*n_ehci
ehci_pciconf_dbg_nptr_reg = [None]*n_ehci
ehci_pciconf_dbg_base_reg = [None]*n_ehci
ehci_pciconf_fladj_reg = [None]*n_ehci
ehci_pciconf_portwakecap_reg = [None]*n_ehci
for i in range(n_ehci):
    ehci_pciconf_vid_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x0, 2)
    ehci_pciconf_did_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x2, 2)
    ehci_pciconf_cmd_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x4, 1)
    ehci_pciconf_memaddr_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x10, 4)
    ehci_pciconf_ioaddr_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x20, 4)
    ehci_pciconf_dbg_capid_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x58, 1)
    ehci_pciconf_dbg_nptr_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x59, 1)
    ehci_pciconf_dbg_base_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x5A, 2)
    ehci_pciconf_fladj_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x61, 1)
    ehci_pciconf_portwakecap_reg[i] = du.Register_LE(ehci_list[i].bank.pci_config, 0x62, 2)
#
uhci_pciconf_vid_reg = [None]*n_uhci
uhci_pciconf_did_reg = [None]*n_uhci
uhci_pciconf_cmd_reg = [None]*n_uhci
uhci_pciconf_memaddr_reg = [None]*n_uhci
uhci_pciconf_ioaddr_reg = [None]*n_uhci
for i in range(n_uhci):
    uhci_pciconf_vid_reg[i] = du.Register_LE(uhci_list[i].bank.pci_config, 0x0, 2)
    uhci_pciconf_did_reg[i] = du.Register_LE(uhci_list[i].bank.pci_config, 0x2, 2)
    uhci_pciconf_cmd_reg[i] = du.Register_LE(uhci_list[i].bank.pci_config, 0x4, 1)
    uhci_pciconf_memaddr_reg[i] = du.Register_LE(uhci_list[i].bank.pci_config, 0x10, 4)
    uhci_pciconf_ioaddr_reg[i] = du.Register_LE(uhci_list[i].bank.pci_config, 0x20, 4)

########
#
# EHCI I/O registers
#
# CAPLENGTH - Host Controller Capability Registers Length
ehci_caplength_reg = [None]*n_ehci
# HCIVERSION - Host Controller Interface Version Number
ehci_hciversion_reg = [None]*n_ehci
# HCSPARAMS - Host Controller Structural Parameters Register
ehci_hcsparams_reg = [None]*n_ehci
# HCCPARAMS - Host Controller Capability Parameters Register
ehci_hccparams_reg = [None]*n_ehci
# USBCMD - USB Command Register
ehci_usbcmd_reg = [None]*n_ehci
# USBSTS - USB Status Register
ehci_usbsts_reg = [None]*n_ehci
# USBINTR - USB Interrupt Enable Register
ehci_usbintr_reg = [None]*n_ehci
# FRINDEX - USB Frame Index Register
ehci_frindex_reg = [None]*n_ehci
# CTRLDSSEGMENT - 4G Segment Selector
ehci_ctrlseg_reg = [None]*n_ehci
# PERIODICLISTBASE - Frame List Base Address
ehci_prdlstbase_reg = [None]*n_ehci
# ASYNCLISTADDR - Next Asynchronous List Address
ehci_asynclsta_reg = [None]*n_ehci
# CFGFLAG - Config Flag Register
ehci_cfgflag_reg = [None]*n_ehci
# PORTSC - Port Status and Control Register
n_ports = 6
ehci_portsc_reg = [None]*n_ehci*n_ports
#
for i in range(n_ehci):
    ehci_caplength_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x0, 1)
    ehci_hciversion_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x2, 2)
    ehci_hcsparams_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x4, 4,
                                           du.Bitfield({'reserved1': (31,24),
                                                        'dbg_port_nr': (23,20),
                                                        'reserved2': (19,17),
                                                        'p_indicator': 16,
                                                        'n_cc': (15,12),
                                                        'n_pcc': (11,8),
                                                        'port_route_rules': 7,
                                                        'reserved3': (6,5),
                                                        'port_power_ctrl': 4,
                                                        'n_ports': (3,0)}))
    ehci_hccparams_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x8, 4,
                                           du.Bitfield({'reserved1': (31,16),
                                                        'eecp': (15,8),
                                                        'iso_sched_thr': (7,4),
                                                        'reserved2': 3,
                                                        'asynch_sched_park_cap': 2,
                                                        'pfl_flag': 1,
                                                        '64b_addr_cap': 0}))
    ehci_usbcmd_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x20, 4,
                                        du.Bitfield({'reserved1': (31,24),
                                                     'int_threshold_ctrl': (23,16),
                                                     'reserved2': (15,12),
                                                     'asynch_sched_park_mode_ena': 11,
                                                     'reserved3': 10,
                                                     'asynch_sched_park_mode_cnt': (9,8),
                                                     'light_hcreset': 7,
                                                     'int_asynch_adv_doorbell': 6,
                                                     'asynch_sched_ena': 5,
                                                     'period_sched_ena': 4,
                                                     'frame_list_size': (3,2),
                                                     'hcreset': 1,
                                                     'run_stop': 0}))
    ehci_usbsts_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x24, 4,
                                        du.Bitfield({'reserved1': (31,16),
                                                     'asynch_sched_status': 15,
                                                     'period_sched_status': 14,
                                                     'reclamation': 13,
                                                     'hchalted': 12,
                                                     'reserved2': (11,6),
                                                     'int_asynch_adv': 5,
                                                     'hserror': 4,
                                                     'frame_list_rollover': 3,
                                                     'port_change_detect': 2,
                                                     'usb_error_int': 1,
                                                     'usb_int': 0}))
    ehci_usbintr_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x28, 4)
    ehci_frindex_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x2C, 4,
                                         du.Bitfield({'reserved': (31,14),
                                                      'frame_nr': (13,3),
                                                      'microframe_nr': (2,0)}))
    ehci_ctrlseg_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x30, 4)
    ehci_prdlstbase_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x34, 4)
    ehci_asynclsta_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x38, 4)
    ehci_cfgflag_reg[i] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x60, 4,
                                         du.Bitfield({'reserved': (31,1),
                                                      'configure_flag': 0}))
    for j in range(n_ports):
        k = i*n_ports + j
        ehci_portsc_reg[k] = du.Register_LE(ehci_list[i].bank.usb_regs, 0x64 + 4*j, 4,
                                            du.Bitfield({'reserved1': (31,23),
                                                         'wkoc_ena': 22,
                                                         'wkdscnnt_ena': 21,
                                                         'wkcnnt_ena': 20,
                                                         'port_test_ctrl': (19,16),
                                                         'port_ind_ctrl': (15,14),
                                                         'port_owner': 13,
                                                         'port_power': 12,
                                                         'line_status': (11,10),
                                                         'reserved2': 9,
                                                         'port_reset': 8,
                                                         'suspend': 7,
                                                         'force_port_resume': 6,
                                                         'over-current_chg': 5,
                                                         'over-current_act': 4,
                                                         'port_ena_chg': 3,
                                                         'port_ena': 2,
                                                         'conn_status_chg': 1,
                                                         'curr_conn_status': 0}))
########
#
# UHCI registers
#
# PORTSC - Port Status and Control Register
uhci_usbcmd_reg = [None]*n_uhci
uhci_usbsts_reg = [None]*n_uhci
uhci_usbintr_reg = [None]*n_uhci
uhci_portsc_reg = [None]*n_uhci*2
for i in range(n_uhci):
    uhci_usbcmd_reg[i] = du.Register_LE(uhci_list[i].bank.usb_regs, 0x00, 2,
                                        du.Bitfield({'reserved': (15,8),
                                                     'max_packet': 7,
                                                     'configure_flag': 6,
                                                     'sw_debug': 5,
                                                     'fgr': 4,
                                                     'egsm': 3,
                                                     'greset': 2,
                                                     'hcreset': 1,
                                                     'run_stop': 0}))
    uhci_usbsts_reg[i] = du.Register_LE(uhci_list[i].bank.usb_regs, 0x02, 2,
                                        du.Bitfield({'reserved': (15,6),
                                                     'hchalted': 5,
                                                     'hc_proc_error': 4,
                                                     'host_system_error': 3,
                                                     'resume_detect': 2,
                                                     'usb_error_int': 1,
                                                     'usb_int': 0}))
    uhci_usbintr_reg[i] = du.Register_LE(uhci_list[i].bank.usb_regs, 0x04, 2,
                                        du.Bitfield({'reserved': (15,4),
                                                     'spi_enable': 3,
                                                     'ioc_enable': 2,
                                                     'ri_enable': 1,
                                                     'ti_enable': 0}))
    uhci_portsc_reg[i*2] = du.Register_LE(uhci_list[i].bank.usb_regs, 0x10, 2,
                                          du.Bitfield({'reserved1': (15,13),
                                                       'suspend': 12,
                                                       'reserved2': (11,10),
                                                       'port_reset': 9,
                                                       'low_speed_dev_att': 8,
                                                       'reserved3': 7,
                                                       'resume_detect': 6,
                                                       'line_status': (5,4),
                                                       'port_ena_chg': 3,
                                                       'port_ena': 2,
                                                       'conn_status_chg': 1,
                                                       'curr_conn_status': 0}))
    uhci_portsc_reg[i*2+1] = du.Register_LE(uhci_list[i].bank.usb_regs, 0x12, 2,
                                            du.Bitfield({'reserved1': (15,13),
                                                         'suspend': 12,
                                                         'reserved2': (11,10),
                                                         'port_reset': 9,
                                                         'low_speed_dev_att': 8,
                                                         'reserved3': 7,
                                                         'resume_detect': 6,
                                                         'line_status': (5,4),
                                                         'port_ena_chg': 3,
                                                         'port_ena': 2,
                                                         'conn_status_chg': 1,
                                                         'curr_conn_status': 0}))

########
#
# Register default value list
#
ehci_reg_defaults = [
    [ehci_caplength_reg[0], 0x00000020],
    [ehci_caplength_reg[1], 0x00000020],
    [ehci_hciversion_reg[0], 0x00000100],
    [ehci_hciversion_reg[1], 0x00000100],
    [ehci_hcsparams_reg[0], 0x00103206],
    [ehci_hcsparams_reg[1], 0x00103206],
    [ehci_hccparams_reg[0], 0x00006871],
    [ehci_hccparams_reg[1], 0x00006871],
    [ehci_usbcmd_reg[0], 0x00080000],
    [ehci_usbcmd_reg[1], 0x00080000],
    [ehci_usbsts_reg[0], 0x00001000],
    [ehci_usbsts_reg[1], 0x00001000],
    [ehci_usbintr_reg[0], 0x00000000],
    [ehci_usbintr_reg[1], 0x00000000],
    [ehci_frindex_reg[0], 0x00000000],
    [ehci_frindex_reg[1], 0x00000000],
    [ehci_ctrlseg_reg[0], 0x00000000],
    [ehci_ctrlseg_reg[1], 0x00000000],
    [ehci_prdlstbase_reg[0], 0x00000000],
    [ehci_prdlstbase_reg[1], 0x00000000],
    [ehci_asynclsta_reg[0], 0x00000000],
    [ehci_asynclsta_reg[1], 0x00000000],
    [ehci_cfgflag_reg[0], 0x00000000],
    [ehci_cfgflag_reg[1], 0x00000000],
    [ehci_portsc_reg[0], 0x00003000],
    [ehci_portsc_reg[1], 0x00003000],
    [ehci_portsc_reg[2], 0x00003000],
    [ehci_portsc_reg[3], 0x00003000],
    [ehci_portsc_reg[4], 0x00003000],
    [ehci_portsc_reg[5], 0x00003000],
    [ehci_portsc_reg[6], 0x00003000],
    [ehci_portsc_reg[7], 0x00003000],
    [ehci_portsc_reg[8], 0x00003000],
    [ehci_portsc_reg[9], 0x00003000],
    [ehci_portsc_reg[10], 0x00003000],
    [ehci_portsc_reg[11], 0x00003000],
    [ehci_pciconf_vid_reg[0], 0x00000000],
    [ehci_pciconf_vid_reg[1], 0x00000000],
    [ehci_pciconf_did_reg[0], 0x00000000],
    [ehci_pciconf_did_reg[1], 0x00000000],
    [ehci_pciconf_cmd_reg[0], 0x00000000],
    [ehci_pciconf_cmd_reg[1], 0x00000000],
    [ehci_pciconf_memaddr_reg[0], 0x00000000],
    [ehci_pciconf_memaddr_reg[1], 0x00000000],
    [ehci_pciconf_ioaddr_reg[0], 0x00000000],
    [ehci_pciconf_ioaddr_reg[1], 0x00000000],
    [ehci_pciconf_dbg_capid_reg[0], 0x00000012],
    [ehci_pciconf_dbg_capid_reg[1], 0x00000012],
    [ehci_pciconf_dbg_nptr_reg[0], 0x00000230],
    [ehci_pciconf_dbg_nptr_reg[1], 0x00000230],
    [ehci_pciconf_dbg_base_reg[0], 0x01000012],
    [ehci_pciconf_dbg_base_reg[1], 0x01000012],
    [ehci_pciconf_fladj_reg[0], 0x00000000],
    [ehci_pciconf_fladj_reg[1], 0x00000000],
    [ehci_pciconf_portwakecap_reg[0], 0x00000000],
    [ehci_pciconf_portwakecap_reg[1], 0x00000000],
    ]

uhci_reg_defaults = [
    [uhci_usbcmd_reg[0], 0x00000000],
    [uhci_usbcmd_reg[1], 0x00000000],
    [uhci_usbcmd_reg[2], 0x00000000],
    [uhci_usbcmd_reg[3], 0x00000000],
    [uhci_usbcmd_reg[4], 0x00000000],
    [uhci_usbcmd_reg[5], 0x00000000],
    [uhci_usbsts_reg[0], 0x00000000],
    [uhci_usbsts_reg[1], 0x00000000],
    [uhci_usbsts_reg[2], 0x00000000],
    [uhci_usbsts_reg[3], 0x00000000],
    [uhci_usbsts_reg[4], 0x00000000],
    [uhci_usbsts_reg[5], 0x00000000],
    [uhci_usbintr_reg[0], 0x00000000],
    [uhci_usbintr_reg[1], 0x00000000],
    [uhci_usbintr_reg[2], 0x00000000],
    [uhci_usbintr_reg[3], 0x00000000],
    [uhci_usbintr_reg[4], 0x00000000],
    [uhci_usbintr_reg[5], 0x00000000],
    [uhci_portsc_reg[0], 0x00000080],
    [uhci_portsc_reg[1], 0x00000080],
    [uhci_portsc_reg[2], 0x00000080],
    [uhci_portsc_reg[3], 0x00000080],
    [uhci_portsc_reg[4], 0x00000080],
    [uhci_portsc_reg[5], 0x00000080],
    [uhci_portsc_reg[6], 0x00000080],
    [uhci_portsc_reg[7], 0x00000080],
    [uhci_portsc_reg[8], 0x00000080],
    [uhci_portsc_reg[9], 0x00000080],
    [uhci_portsc_reg[10], 0x00000080],
    [uhci_portsc_reg[11], 0x00000080],
    [uhci_pciconf_vid_reg[0], 0x00000000],
    [uhci_pciconf_vid_reg[1], 0x00000000],
    [uhci_pciconf_did_reg[0], 0x00000000],
    [uhci_pciconf_did_reg[1], 0x00000000],
    [uhci_pciconf_cmd_reg[0], 0x00000000],
    [uhci_pciconf_cmd_reg[1], 0x00000000],
    [uhci_pciconf_memaddr_reg[0], 0x00000000],
    [uhci_pciconf_memaddr_reg[1], 0x00000000],
    [uhci_pciconf_ioaddr_reg[0], 0x00000000],
    [uhci_pciconf_ioaddr_reg[1], 0x00000000],
    ]

######
#
# Memory operation methods
#
def read_mem(addr, size):
    return mem_iface.read(None, addr, size, 0)

def write_mem(addr, bytes):
    mem_iface.write(None, addr, bytes, 0)

######
#
# Test methods
#
def expect(result, expected, description):
    stest.expect_true(result == expected, description)
