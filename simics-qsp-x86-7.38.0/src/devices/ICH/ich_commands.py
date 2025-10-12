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


from cli import (
    CliError,
    arg,
    flag_t,
    new_command,
    new_info_command,
    new_status_command,
    range_t,
    )
import sim_commands
import usb_commands

enabled_tuple = ("Disabled", "Enabled")
yes_no_tuple = ("No", "Yes")

#
# ---------------------- Thermal sensor info/status -----------------
#

def get_thermal_info(obj):
    pci_info = sim_commands.get_pci_info(obj)
    thermal_info = [("Thermal sensor information",
                    [("Mapped memory base address",
            "0x%x" % (obj.pci_config_thermal_base_addr & ~((1 << 12) - 1))),
                    ]),
                 ]
    return pci_info + thermal_info

def get_thermal_status(obj):
    pci_status = sim_commands.get_pci_status(obj)
    thermal_status = []
    for i in range(2):
        is_sensing = obj.thermal_func_sensor_tse[i] == 0xBA
        thermal_status = thermal_status + \
                [("Thermal sensor %d status" % i,
                   [("Sensing", enabled_tuple[is_sensing]),
                    ("Catastrophic Trip Point",
        obj.thermal_func_sensor_tsttp[i]),
                    ("Whether temperature is above the trip point",
        ("Unknown",
            yes_no_tuple[(obj.thermal_func_sensor_tss[i] >> 7) & 0x1])
                [is_sensing]),
                   ]),
                ]
    return pci_status + thermal_status

#
# ------------------------- SMBus info/status -----------------------
#

def get_smbus_info(obj):
    pci_info = [("PCI information", [('PCI bus', obj.upstream_target),
                                     ('Expansion ROM', "none")])]
    io_on = obj.bank.pcie_config.command & 1
    mem_on = obj.bank.pcie_config.command & 2
    pci_info += [(None,
                        [ ("Memory mappings",
                           "enabled" if mem_on else "disabled"),
                          ("IO mappings", "enabled" if io_on else "disabled")])]
    smbus_info = [("SMBus host controller information",
                    [("Mapped 32-byte SRAM base address",
            "0x%x" % (obj.bank.pcie_config.smbus_sram_bar & ~((1 << 8) - 1))),
                     ("SMBus slave device address",
            obj.bank.smbus_func.notify_daddr >> 1),
                    ]),
                 ]
    return pci_info + smbus_info

def get_smbus_status(obj):
    smb_cmd_tuple = ("Quick", "Byte", "Byte Data", "Word Data", "Process Call",
                     "Block", "I2C Read", "Block Process")
    is_busy = obj.bank.smbus_func.hst_sts & 0x1
    smbus_status = [("SMBus host controller status",
                      [("Executing",
            enabled_tuple[obj.bank.pcie_config.host_configuration & 0x1]),
                       ("SMB interrupting",
            enabled_tuple[(obj.bank.pcie_config.host_configuration >> 1) & 0x1]),
                       ("Busy", yes_no_tuple[is_busy]),
                       ("Current SMBus command",
                        ("None",
            smb_cmd_tuple[(obj.bank.smbus_func.hst_cnt >> 2) & 0x7])[is_busy]),
                      ]),
                   ]

    return smbus_status

#
# ------------------------- Timer info/status -----------------------
#

def get_timer_info(obj):
    timer_info = [("8254 timer I/O base address", "0x%x"%0x40)]
    return [(None, timer_info)]

def get_timer_status(obj):
    timer_status = []
    binary_bcd_tuple = ("binary", "BCD")
    for i in range(3):
        timer_status = timer_status + \
                        [("timer %d started" % i,
            yes_no_tuple[(obj.fixed_io_counters_status[i] >> 6) & 0x1]),
                         ("timer %d mode" % i,
            "Mode %d" % ((obj.fixed_io_counters_status[i] >> 1) & 0x7)),
                         ("timer %d current count" % i,
            "0x%x" % obj.fixed_io_counters_counter[i]),
                         ("timer %d binary/BCD countdown" % i,
            binary_bcd_tuple[obj.fixed_io_counters_status[i] & 0x1]),
                        ]

    return [(None, timer_status)]

#
# ------------------------- RTC info/status -----------------------
#

def get_rtc_info(obj):
    addr = 0x70
    rtc_info = [("RTC base address", "0x%x" % addr)]
    return [(None, rtc_info)]

def get_rtc_status(obj):
    bcd_binary_tuple = ("BCD", "Binary")
    hours_tuple = ("12H", "24H")
    rtc_status = [("RTC current time", obj.time),
                  ("RTC hours format", hours_tuple[(obj.rtc_reg_b >> 1) & 0x1]),
                  ("RTC data Mode",
                        bcd_binary_tuple[(obj.rtc_reg_b >> 2) & 0x1]),
                 ]

    return [(None, rtc_status)]

#
# ------------------------- LPC sum-up info/status -----------------------
#

def get_lpc_info(obj):
    pci_info  = sim_commands.get_pci_info(obj)
    return pci_info

def get_lpc_status(obj):
    pci_status  = sim_commands.get_pci_status(obj)
    fwhi_status = get_lpc_fwhi_status(obj)
    return pci_status + [("FWH Interface", fwhi_status)]
#
# ------------------------- LPC fwhi connect info/status ----------------------
#
def get_lpc_fwhi_status(obj):
    return_list = []
    i = 0
    for dev in obj.fwh_device:
        if (dev != None):
            item = ('connect device_%d' %i, dev)
            return_list.append(item)
        i += 1

    return return_list

#
# ------------------------- LAN controller info/status -----------------------
#
def get_lan_info(obj):
    pci_info = sim_commands.get_pci_info(obj)
    # The value read from the registers is same as that read from the 6-byte
    # DA/SA in the ethernet frame header as a big-endian number
    addr_val = (obj.csr_ra_high[0] << 32) + obj.csr_ra_low[0]
    addr = list((addr_val >> n*8) & 0xff for n in range(6))
    lan_info = [
                ("LAN controller information",
                 [("Speed",
                   ("10Mbps","100Mbps","1000Mbps")[(obj.csr_ctrl >> 8) & 0x3]),
                  ("Duplex",
                   ("Half", "Full")[obj.csr_ctrl & 0x1]),
                  ("MAC address",
                   "%02X:%02X:%02X:%02X:%02X:%02X"
                    % (addr[0], addr[1], addr[2], addr[3], addr[4], addr[5])),
                 ]),
               ]
    return pci_info + lan_info

def get_lan_status(obj):
    pci_status = sim_commands.get_pci_status(obj)
    if "csr_lsecrxctrl" in dir(obj):
        lan_status = [
            ("LAN controller status",
             [("Receive",
               enabled_tuple[(obj.csr_rctl >> 1) & 0x1]),
              ("Transmit",
               enabled_tuple[(obj.csr_tctl >> 1) & 0x1]),
              ("LinkSec RX",
               enabled_tuple[((obj.csr_lsecrxctrl >> 2) & 0x3) != 0]),
              ("LinkSec TX",
               enabled_tuple[(obj.csr_lsectxctrl & 0x3) != 0]),
              ("TimeSync RX",
               enabled_tuple[((obj.csr_tsyncrxctl >> 4) & 0x1) != 0]),
              ("TimeSync TX",
               enabled_tuple[((obj.csr_tsynctxctl >> 4) & 0x1) != 0]),
              ("Received packets",
               obj.csr_gprc),
              ("Transmitted packets",
               obj.csr_gptc),
              ]),
            ]
    else:
        # ICH9 does not have Linksec or Timesync
        lan_status = [
            ("LAN controller status",
             [("Receive",
               enabled_tuple[(obj.csr_rctl >> 1) & 0x1]),
              ("Transmit",
               enabled_tuple[(obj.csr_tctl >> 1) & 0x1]),
              ("Received packets",
               obj.csr_gprc),
              ("Transmitted packets",
               obj.csr_gptc),
              ]),
            ]

    return pci_status + lan_status

#
# ------------------------ HPE Timer info/status ------------------------------
#
def get_hpet_info(obj):
    return [("", [("Number of timers", ((obj.regs_gcap_id >> 8) & 0x1F) + 1),
                   ("Connected 8259", obj.intc_8259),
                   ("Connected APIC", obj.intc_apic),
                  ])]

def get_hpet_status(obj):
    num = ((obj.regs_gcap_id >> 8) & 0x1F) + 1
    st = []
    for i in range(num):
        v = []
        if obj.regs_tim_conf[i] & (1 << 2):
            v.append("Enabled")
        else:
            v.append("Disabled")
        if (obj.regs_tim_conf[i] & (1 << 14)):
            v.append("FSB")
            x = obj.regs_fsb_int_rout[i]
            v.append("[0x%x @ 0x%08x]" % (x & 0xffffffff, (x >> 32)))
        else:
            if (obj.regs_tim_conf[i] & (1 << 1)):
                v.append("Level")
            else:
                v.append("Edge")
            if i < 2 and (obj.regs_gen_conf & (1 << 1)):
                route = "Legacy IRQ[%s]" % ("0/2", "8")[i]
            else:
                route = "IRQ[%d]" % ((obj.regs_tim_conf[i] >> 9) & 0x1f)
            v.append(route)
        if obj.regs_tim_conf[i] & (1 << 8):
            v.append("32-bit")
        if obj.regs_tim_conf[i] & (1 << 6):
            v.append("VAL-SET-CONF")
        if obj.regs_tim_conf[i] & (1 << 3):
            v.append("Periodic")
        st.append(("Timer%d" % i, " ".join(v)))

    cmp = []
    for i in range(num):
        v = []
        mask = 0xffffffff
        if (obj.regs_tim_conf[i] & 0x120) == 0x20:
            mask = 0xffffffffffffffff
        v.append("0x%x" % (obj.regs_tim_comp[i] & mask))
        if obj.regs_tim_conf[i] & (1 << 3):
            period = float(obj.regs_tim_period[i] * (obj.regs_gcap_id >> 32))
            if period != 0:
                freq = 1e15 / period
                v.append("  (periodic @ %.2f Hz)" % freq)
            else:
                v.append("  PERIOD = 0")
        elif obj.regs_tim_conf[i] & (1 << 2):
            val = (obj.regs_tim_comp[i] - obj.regs_running_main_cnt) & mask
            ms = 1e-12 * float(val * (obj.regs_gcap_id >> 32))
            v.append("  (expires in %.3f ms)" % ms)
        cmp.append(("Timer%d" % i, " ".join(v)))

    gst = [
        ('State', ("Halted", "Running")[obj.regs_gen_conf & 1]),
        ]

    v , q = [], []
    for i in range(num):
        sbit = (obj.regs_gintr_sta & (1 << i))
        if sbit:
            v.append("Timer%d" % i)

        pin = obj.regs_irq_pins[i]
        valid, apic, i8259 = (pin >> 16) & 1, (pin & 0xff), (pin >> 8) & 0xff
        if valid:
            if apic == i8259:
                q.append("IRQ[%d]" % (apic))
            else:
                q.append("IRQ[%d/%d]" % (i8259, apic))

    gst.append(("Status", " ".join(v)))
    gst.append(("IRQ Pins", " ".join(q)))
    gst.append(('Counter', "0x%x" % obj.regs_running_main_cnt))

    return [("Configuration", st),
            ("State", gst),
            ("Comparators", cmp),
            ]

#
# ------------------------ dmi2pci info/status -------------------------
#
def get_bridge_info(obj):
    return []

def get_bridge_status(obj):
    return []


#
# ------------------------- SATA_F2 info/status -------------------------
#
def get_sata_f2_info(obj):
    sata_info = [("address map",
                  [("pcmd bar", "0x%x"%(obj.pci_config_pcmd_bar & 0xfffffffe)),
                   ("pcnl bar", "0x%x"%(obj.pci_config_pcnl_bar & 0xfffffffe)),
                   ("scmd bar", "0x%x"%(obj.pci_config_scmd_bar & 0xfffffffe)),
                   ("scnl bar", "0x%x"%(obj.pci_config_scnl_bar & 0xfffffffe)),
                   ("legacy bar", "0x%x"%(obj.pci_config_bar & 0xfffffffe))
                  ])]
    sata_device = []
    for i in range(32):
        if obj.sata_device[i]:
            sata_device.append(['sata_device[%d]' % i, obj.sata_device[i]])
    return sata_info + [(None, [("connected SATA device", sata_device)])]

def get_sata_f2_status(obj):
    mode_list = ["IDE", "AHCI", "RAID"]
    irq_pin = obj.pci_config_interrupt_pin - 1
    irq_raised = (obj.pci_config_interrupts >> irq_pin) & 1
    mode_status = [("Work Mode ", mode_list[(obj.pci_config_map >> 6) & 0x3]),
                   ("IRQ status", "raised" if irq_raised else "lowered")
                  ]

    return [("SATA status ", mode_status)]

#
# ------------------------- SATA_F5 info/status -------------------------
#
def get_sata_f5_info(obj):
    sata_info = [("address map",
                  [("pcmd bar", "0x%x"%(obj.pci_config_pcmd_bar & 0xfffffffe)),
                   ("pcnl bar", "0x%x"%(obj.pci_config_pcnl_bar & 0xfffffffe)),
                   ("scmd bar", "0x%x"%(obj.pci_config_scmd_bar & 0xfffffffe)),
                   ("scnl bar", "0x%x"%(obj.pci_config_scnl_bar & 0xfffffffe)),
                   ("legacy bar", "0x%x"%(obj.pci_config_bar & 0xfffffffe))
                  ])]
    return sata_info

def get_sata_f5_status(obj):
    return []

#-------------------------- RTC command ------------------------

# Access functions for the NVRAM

def nvram_read(obj, offset):
    return obj.rtc_ram[offset - 14]

def nvram_write(obj, offset, value):
    nvram_values = obj.rtc_ram
    nvram_values[offset - 14] = value
    obj.rtc_ram = nvram_values

# CMOS checksum calculation

def cmos_checksum(obj):
    sum = 0
    for i in range(0x10, 0x2e):
        sum = sum + nvram_read(obj, i)
    nvram_write(obj, 0x2e, (sum >> 8) & 0xff)
    nvram_write(obj, 0x2f, sum & 0xff)

# Optionally convert value to bcd format, depending on the DM bit
def reg_value(obj, value):
    if nvram_read(obj, 11) & 0x4:
        # binary
        return value
    else:
        #bcd
        hi = value // 10
        lo = value - (hi * 10)
        return hi << 4 | lo

#
# -------------------- set-date-time --------------------
#

def set_date_time_cmd(obj, year, month, mday, hour, minute, second,
                      binary, bcd):
    if binary:
        obj.rtc_reg_a = obj.rtc_reg_a | 0x4
    elif bcd:
        obj.rtc_reg_a = obj.rtc_reg_a & ~0x4

    try:
        obj.time = "%02d-%02d-%02d %02d:%02d:%02d" % (year % 100, month, mday,
                                                      hour, minute, second)
    except:
        raise CliError("Could not set time")
    # TODO: Set century if stored in CMOS

#
# -------------------- get-date-time --------------------
#

def get_date_time_cmd(obj):
    print("Time: %s" % obj.time)

#
# --------------------- SPI -------------------------------
#

def get_spi_info(obj):
    spi_info = [("spi information",
                    [("Is Descriptor Mode",
                            yes_no_tuple[(obj.spi_regs_hsfsts >> 14) & 0x1]),
                    ]),
               ]
    return spi_info

def get_spi_status(obj):
    return []

def register_common_ich_commands(device_prefix):
    new_info_command('%s_thermal' % device_prefix, get_thermal_info)
    new_status_command('%s_thermal' % device_prefix, get_thermal_status)

    new_info_command('%s_smbus' % device_prefix, get_smbus_info)
    new_status_command('%s_smbus' % device_prefix, get_smbus_status)

    new_info_command('%s_smbus_i2c_v2' % device_prefix, get_smbus_info)
    new_status_command('%s_smbus_i2c_v2' % device_prefix, get_smbus_status)

    new_info_command('%s_lpc' % device_prefix, get_lpc_info)
    new_status_command('%s_lpc' % device_prefix, get_lpc_status)

    new_info_command('%s_usb_uhci' % device_prefix,
                     usb_commands.get_usb_uhci_info)
    new_status_command('%s_usb_uhci' % device_prefix,
                       usb_commands.get_usb_uhci_status)

    new_info_command('%s_usb_ehci' % device_prefix,
                     usb_commands.get_usb_ehci_info)
    new_status_command('%s_usb_ehci' % device_prefix,
                       usb_commands.get_usb_ehci_status)
    usb_commands.register_usb_ehci_descriptors_command(
        '%s_usb_ehci' % device_prefix)

    new_info_command('%s_rtc' % device_prefix, get_rtc_info)
    new_status_command('%s_rtc' % device_prefix, get_rtc_status)

    new_info_command('%s_timer' % device_prefix, get_timer_info)
    new_status_command('%s_timer' % device_prefix, get_timer_status)

    new_info_command('%s_bridge' % device_prefix, get_bridge_info)
    new_status_command('%s_bridge' % device_prefix, get_bridge_status)

    new_info_command('%s_hpe_timer' % device_prefix, get_hpet_info)
    new_status_command('%s_hpe_timer' % device_prefix, get_hpet_status)

    new_info_command('%s_sata_f2' % device_prefix, get_sata_f2_info)
    new_status_command('%s_sata_f2' % device_prefix, get_sata_f2_status)

    new_info_command('%s_sata_f5' % device_prefix, get_sata_f5_info)
    new_status_command('%s_sata_f5' % device_prefix, get_sata_f5_status)

    new_command("set-date-time", set_date_time_cmd,
                [arg(range_t(1970, 2037, "1970..2037"), "year"),
                 arg(range_t(1, 12, "1..12"), "month"),
                 arg(range_t(1, 31, "1..31"), "mday"),
                 arg(range_t(0, 23, "0..23"), "hour"),
                 arg(range_t(0, 59, "0..59"), "minute"),
                 arg(range_t(0, 59, "0..59"), "second"),
                 arg(flag_t, "-binary"), arg(flag_t, "-bcd")],
                short = "set date and time",
                cls = device_prefix + "_rtc",
                doc = """
Set the date and time of the realtime clock. Both <arg>month</arg> and
<arg>mday</arg> start counting at one while <arg>hour</arg>,
<arg>minute</arg> and <arg>second</arg>, start at zero.
The <arg>year</arg> argument should be in the full four-digit format.

The <cmd>&lt;x86-component&gt;.cmos-init</cmd> command must be issued before
this command, unless the simulation was started from a checkpoint.

The <tt>-binary</tt> and <tt>-bcd</tt> flags can be used to specify the format
of the register values. Default is to use BCD, but some systems use a binary
format without checking the binary/BCD status bit in register B.
""")

    new_command("get-date-time", get_date_time_cmd,
                [],
                short = "get date and time",
                cls = device_prefix + "_rtc",
                doc = """
    Return the date and time of the realtime clock.<br/>
    """)

    new_info_command('%s_spi' % device_prefix, get_spi_info)
    new_status_command('%s_spi' % device_prefix, get_spi_status)

#
# --------------------- CF9 -------------------------------
#

def get_cf9_info(obj):
    return [(None, [("Reset target", obj.reset_signal)])]

def get_cf9_status(obj):
    return []
