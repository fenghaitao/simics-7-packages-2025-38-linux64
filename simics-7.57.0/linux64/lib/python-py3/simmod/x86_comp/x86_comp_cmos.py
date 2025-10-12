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


import cli
import simics

# NV-RAM offset and attribute mapping
nvram_info = {"DS12887-c": (0, 'nvram', None, None),
              "DS17485": (0, 'nvram', None, None), # Same as DS17485-c
              "DS12887": (-14, 'registers_nvram', 'registers_volatile_ram',
                           'registers_ram_ctrl'),
              "generic_rtc": (-14, 'rtc_ram', 'rtc_volatile_ram', 'rtc_ram_ctrl'),
              "ich10_rtc": (-14, 'rtc_ram', 'rtc_volatile_ram', 'rtc_ram_ctrl'),
              "ich9r_rtc": (-14, 'rtc_ram', 'rtc_volatile_ram', 'rtc_ram_ctrl'),
              "sch_rtc": (-14, 'rtc_ram', None, None), # Needed by Wind River
              "pch_rtc": (-14, 'rtc_ram', None, None), # Needed by Wind River
              }

def nvram_read(rtc, offset):
    try:
        (start, attr, vol_attr, ctrl) = nvram_info[rtc.classname]
        offset += start
        if vol_attr:
            if getattr(rtc, ctrl)[offset] == 0:
                return getattr(rtc, attr)[offset]
            else:
                return getattr(rtc, vol_attr)[offset]
        else:
            return getattr(rtc, attr)[offset]
    except KeyError:
        print("Unknown real-time clock class: %s" % rtc.classname)

def nvram_write(rtc, offset, value, volatile = False):
    try:
        (start, attr, vol_attr, ctrl) = nvram_info[rtc.classname]
        offset += start
        getattr(rtc, attr)[offset] = value
        if vol_attr:
            getattr(rtc, vol_attr)[offset] = value
            if volatile:
                getattr(rtc, ctrl)[offset] = 1
    except KeyError:
        print("Unknown real-time clock class: %s" % rtc.classname)

def nvram_write_volatile(rtc, offset, value):
    nvram_write(rtc, offset, value, True)

# CMOS checksum calculation
def cmos_checksum(rtc):
    sum = 0
    for i in range(0x10, 0x2e):
        sum = sum + nvram_read(rtc, i)
    # write checksum
    nvram_write(rtc, 0x2e, (sum >> 8) & 0xff)
    nvram_write(rtc, 0x2f, sum & 0xff)

# Conditionally convert value to bcd format, depending on the DM bit

def reg_value(rtc, value):
    if nvram_read(rtc, 11) & 0x4:
        # binary
        return value
    else:
        #bcd
        hi = value // 10
        lo = value - (hi * 10)
        return hi << 4 | lo

def default_get_rtc(obj):
    try:
        rtc = simics.SIM_get_object(obj.name + '.southbridge.rtc')
    except simics.SimExc_General:
        try:
            rtc = simics.SIM_get_object(obj.name + '.sb.rtc')
        except simics.SimExc_General:
            raise cli.CliError("Component has no RTC")
    return rtc

#
# -------------------- cmos-init --------------------
#

def cmos_init_cmd(obj, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)

    # shutdown status, 0 normal startup
    nvram_write(rtc, 0x0f, 0x00)

    # equipment byte.
    # bit 6-7, number of disk drives, (set later)
    # bit 4-5, video: 0 - vga
    # bit 2,   unused
    # bit 1,   math coprocessor
    # bit 0,   disk drive installed for boot
    nvram_write(rtc, 0x14, 0x07)

    # base memory in kB, always 640
    nvram_write(rtc, 0x15, 640 & 0xff)
    nvram_write(rtc, 0x16, (640 >> 8) & 0xff)

    # system flags:
    # bit 5 - boot A: first, then C:  - A is default
    nvram_write(rtc, 0x2d, 0x20)

    # default century
    cmos_century(rtc, 20)
    cmos_checksum(rtc)

#
# -------------------- cmos-base-mem --------------------
#

def cmos_base_mem_cmd(obj, size, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)
    if size > 640:
        print("Larger than maximal value (640 kB), setting max.")
        size = 640

    # store size in kB
    nvram_write_volatile(rtc, 0x15, size & 0xff)
    nvram_write_volatile(rtc, 0x16, (size >> 8) & 0xff)
    cmos_checksum(rtc)

#
# -------------------- cmos-extended-mem --------------------
#

def cmos_extended_mem_cmd(obj, size, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)

    # store size in kB, saturate to 0xffff
    size_in_k = size * 1024
    if size_in_k > 0xffff:
        size_in_k = 0xffff

    nvram_write_volatile(rtc, 0x17, size_in_k & 0xff)
    nvram_write_volatile(rtc, 0x18, (size_in_k >> 8) & 0xff)
    nvram_write_volatile(rtc, 0x30, size_in_k & 0xff)
    nvram_write_volatile(rtc, 0x31, (size_in_k >> 8) & 0xff)

    # store size in 64 kB chunks above 16 MB (for SeaBIOS)
    size_in_k = size * 1024
    if size_in_k > 16 * 1024:
        if size_in_k > 0xe0000000 // 1024:
            # PCI window starts at 0xe0000000
            size_in_k = 0xe0000000 // 1024
        chunks = (size_in_k // 64) - (16 * 1024 // 64)
        if chunks > 0xffff:
            chunks = 0xffff
        nvram_write_volatile(rtc, 0x34, chunks & 0xff)
        nvram_write_volatile(rtc, 0x35, (chunks >> 8) & 0xff)

    # store size in 64 kB chunks above 4 GB (for SeaBIOS)
    size_in_k = size * 1024
    if size_in_k > 4 * 1024 * 1024:
        chunks = (size_in_k // 64) - (4 * 1024 * 1024 // 64)
        nvram_write_volatile(rtc, 0x5b, chunks & 0xff)
        nvram_write_volatile(rtc, 0x5c, (chunks >> 8) & 0xff)
        nvram_write_volatile(rtc, 0x5d, (chunks >> 16) & 0xff)

    cmos_checksum(rtc)

#
# -------------------- cmos-floppy --------------------
#

disk_types = ["none", "360", "720", "1.2", "1.44", "2.88", "320" ]

def type_expand(string):
    return cli.get_completions(string, disk_types)

def cmos_floppy_cmd(obj, drive, drive_type, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)
    drive = drive.upper()
    if (drive != "A") and (drive != "B"):
        print("Only drive A and B supported")
        return
    try:
        type_num = disk_types.index(drive_type)
    except:
        print("Unknown disk type")
        print("Try one of:")
        print(disk_types)
        raise cli.CliError("Unknown disk type.")

    # high nibble drive 0, low drive 1
    val = nvram_read(rtc, 0x10)
    if drive == "A":
        val = (type_num << 4) | (val & 0x0f)
    else:
        val = type_num | (val & 0xf0)
    nvram_write(rtc, 0x10, val)

    drives = 0
    if val & 0xf0:
        drives = 1
    if val & 0x0f:
        drives = drives + 1

    # equipment byte: bit 6-7, number of disk drives
    val = (drives << 6) | (nvram_read(rtc, 0x14) & 0x3f)
    nvram_write(rtc, 0x14, val)
    cmos_checksum(rtc)


#
# -------------------- cmos-hd --------------------
#

hd_regs = ( (0x19, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23),
            (0x1a, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c) )

def cmos_hd_cmd(obj, drive, cylinders, heads, sectors_per_track, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)
    drive = drive.upper()
    if (drive != "C") and (drive != "D"):
        print("Only drive C and D supported")
        return
    drive_val = 0xf
    if (cylinders == 0) or (heads == 0) or (sectors_per_track == 0):
        if simics.SIM_get_verbose():
            print("[%s] No drive set on: %s" % (rtc.name, drive))
        drive_val = 0x0
        cylinders = 0
        heads = 0
        sectors_per_track = 0

    # Type of hard drive. High nibble drive 0, low nibble drive 1
    # Values: 0x0 - no drive,
    #         0x1 -> 0xe - different type numbers
    #         0xf - read in reg 0x19 instead (0x1a for drive 1).
    val = nvram_read(rtc, 0x12)
    if drive == "C":
        val = (drive_val << 4) | (val & 0x0f)
        drive_num = 0
    else:
        val = (drive_val) | (val & 0xf0)
        drive_num = 1
    nvram_write(rtc, 0x12, val)

    # HD <drive> type, use 47
    if drive_val == 0:
        nvram_write(rtc, hd_regs[drive_num][0], 0x0)
    else:
        nvram_write(rtc, hd_regs[drive_num][0], 0x2f)

    # low and high cylinder word (number of cyls)
    nvram_write(rtc, hd_regs[drive_num][1], cylinders & 0xff)
    nvram_write(rtc, hd_regs[drive_num][2], (cylinders >> 8) & 0xff)
    # number of heads
    nvram_write(rtc, hd_regs[drive_num][3], heads)

    # low precomp cylinder, obsolete set to 0
    nvram_write(rtc, hd_regs[drive_num][4], 0x00)
    nvram_write(rtc, hd_regs[drive_num][5], 0x00)

    # drive control,
    # bit 6, 7 == 0
    # bit 5 - bad map at last cyl + 1, (not used)
    # bit 3 - more that 8 heads
    val = 0x00
    if heads > 8:
        val = val | 0x08
    nvram_write(rtc, hd_regs[drive_num][6], val)

    # low and high landing zone cyl, obsolete set to max cylinder + 1
    nvram_write(rtc, hd_regs[drive_num][7], cylinders & 0xff)
    nvram_write(rtc, hd_regs[drive_num][8], (cylinders >> 8) & 0xff)

    # sectors per track
    nvram_write(rtc, hd_regs[drive_num][9], sectors_per_track)
    cmos_checksum(rtc)

#
# -------------------- cmos-boot-dev --------------------
#

def cmos_boot_dev_cmd(obj, drive, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)
    drive = drive.upper()

    # Virtutech BIOS encoding
    #    0x2d          boot device
    #          0x20     Floppy boot
    #          0x00     Hard drive boot
    #
    # SeaBIOS encoding
    #    0x3d bit 0-3  1st boot device
    #    0x3d bit 4-7  2nd boot device
    #    0x38 bit 4-7  3rd boot device
    #          0x1      Floppy boot
    #          0x2      Hard drive boot
    #          0x3      CD-ROM boot
    #          0x4      Network boot

    # Extend this command to cover multiple boot options, CD-ROM and
    # network when/if we switch to the SeaBIOS as default

    if drive == "A":
        nvram_write(rtc, 0x2d, 0x20) # For Virtutech BIOS
        nvram_write(rtc, 0x3d, 0x01) # For SeaBIOS
    elif drive == "C":
        nvram_write(rtc, 0x2d, 0x00) # For Virtutech BIOS
        nvram_write(rtc, 0x3d, 0x02) # For SeaBIOS
    elif drive == "CD-ROM":
        nvram_write(rtc, 0x3d, 0x03) # For SeaBIOS
    else:
        print("Only A, C, and CD-ROM supported as boot devices")
        return
    cmos_checksum(rtc)


#
# -------------------- cmos-century --------------------
#

def cmos_century(rtc, century):
    nvram_write(rtc, 0x32, reg_value(rtc, century))
    cmos_checksum(rtc)

#
# -------------------- cmos-info -----------------------
#

def cmos_info_cmd(obj, get_rtc = default_get_rtc):
    rtc = get_rtc(obj)
    print()
    print("    Base memory    : %5d kB" % ((nvram_read(rtc, 0x16) << 8) | nvram_read(rtc, 0x15)))
    print("Extended memory (1): %5d kB" % ((nvram_read(rtc, 0x18) << 8) | nvram_read(rtc, 0x17)))
    print("Extended memory (2): %5d kB" % ((nvram_read(rtc, 0x31) << 8) | nvram_read(rtc, 0x30)))
    print()
    print("  Num floppy drives: %d" % ((nvram_read(rtc, 0x14) >> 6) & 0x3))
    try:
        atype = disk_types[nvram_read(rtc, 0x10) >> 4]
    except:
        atype = "Unknown"
    try:
        btype = disk_types[nvram_read(rtc, 0x10) & 0xf]
    except:
        btype = "Unknown"
    print("            A: type: %s" % atype)
    print("            B: type: %s" % btype)
    print()
    drvtype = []
    drvname = ["C", "D"]
    drvtype.append(nvram_read(rtc, 0x12) >> 4)
    drvtype.append(nvram_read(rtc, 0x12) & 0xf)
    for drv in range(0, 2):
        if drvtype[drv] == 0x0:
            print("     %s: Drive type : No disk" % drvname[drv])
        elif drvtype[drv] != 0xf:
            print("     %s: Drive type : 0x%02x (obsolete)" % (drvname[drv], drvtype[drv]))
        else:
            print("     %s: Drive type : 0x%02x" % (drvname[drv], nvram_read(rtc, hd_regs[drv][0])))
            print("         Cylinders : %4d" % ((nvram_read(rtc, hd_regs[drv][2]) << 8) | nvram_read(rtc, hd_regs[drv][1])))
            print("             Heads : %4d" % nvram_read(rtc, hd_regs[drv][3]))
            print(" Sectors per track : %4d" % nvram_read(rtc, hd_regs[drv][9]))
            print()
    print()
    if nvram_read(rtc, 0x2d) == 0x20:
        boot_dev = "A"
    elif nvram_read(rtc, 0x2d) == 0x00:
        boot_dev = "C"
    else:
        boot_dev = "Unknown"
    print("        Boot device (rombios): %s" % boot_dev)
    if (nvram_read(rtc, 0x3d) & 0x0f) == 0x01:
        boot_dev = "A"
    elif (nvram_read(rtc, 0x3d) & 0x0f) == 0x02:
        boot_dev = "C"
    elif (nvram_read(rtc, 0x3d) & 0x0f) == 0x03:
        boot_dev = "CD-ROM"
    elif (nvram_read(rtc, 0x3d) & 0x0f) == 0x04:
        boot_dev = "Network"
    else:
        boot_dev = "Unknown"
    print("        Boot device (Seabios): %s" % boot_dev)
    print()
    reset_code = nvram_read(rtc, 0xf)
    reset_codes = {0x00: "software reset or unexpected reset",
                   0x01: "reset after memory size check",
                   0x02: "reset after successful memory test",
                   0x03: "reset after failed memory test",
                   0x04: "INT 19h reboot",
                   0x05: "flush keyboard (issue EOI) and jump via 40h:0067h",
                   0x06: "reset (after successful test in virtual mode)",
                   0x07: "reset (after failed test in virtual mode)",
                   0x08: "used by POST during protected-mode RAM test",
                   0x09: "used for INT 15/87h (block move) support",
                   0x0A: "resume execution by jump via 40h:0067h",
                   0x0B: "resume execution via IRET via 40h:0067h",
                   0x0C: "resume execution via RETF via 40h:0067h"}
    print("        Reset code : %s" % (reset_codes.get(reset_code,
                                                       "0x%x" % reset_code)))
    print()

def register_cmos_commands(class_name, get_rtc_func = default_get_rtc):
    def cmos_init_cmd_instance(obj):
        cmos_init_cmd(obj, get_rtc = get_rtc_func)

    cli.new_command("cmos-init", cmos_init_cmd_instance,
                [],
                short = "initialize some CMOS values",
                cls = class_name,
                doc = """
Sets initial CMOS values in the RTC device. This is miscellaneous data that is
not set by any of the other cmos-* commands. Note that the CMOS values only has
to be set if not running from a saved configuration. A saved configuration will
have all values stored in the NVRAM area, and the cmos-* commands need only be
used if some values have to be changed.""")

    def cmos_base_mem_cmd_instance(obj, size):
        cmos_base_mem_cmd(obj, size, get_rtc = get_rtc_func)

    cli.new_command("cmos-base-mem", cmos_base_mem_cmd_instance,
                [cli.arg(cli.int_t, "kilobytes")],
                short = "set base memory size",
                cls = class_name,
                doc = """
Sets the CMOS amount of base memory to <arg>kilobytes</arg> KiB. This will
update the proper location in the CMOS so that the BIOS will know how much
memory is installed in the system. Operating system that use the BIOS to find
out the memory size will get confused if this size is set incorrectly
(especially if it is set too high). The maximum amount that can be set is
640kB.""")

    def cmos_extended_mem_cmd_instance(obj, size):
        cmos_extended_mem_cmd(obj, size, get_rtc = get_rtc_func)

    cli.new_command("cmos-extended-mem", cmos_extended_mem_cmd_instance,
                [cli.arg(cli.int_t, "megabytes")],
                short = "set extended memory size",
                cls = class_name,
            doc = """
Sets the amount of extended memory to <arg>megabytes</arg> MiB. This will
update the proper location in the CMOS so that the BIOS will know how much
memory is installed in the system. Operating system that use the BIOS to find
out the memory size will get confused if this size is set incorrectly
(especially if it is set too high).""")

    def cmos_floppy_cmd_instance(obj, drive, drive_type):
        cmos_floppy_cmd(obj, drive, drive_type, get_rtc = get_rtc_func)

    cli.new_command("cmos-floppy", cmos_floppy_cmd_instance,
                [cli.arg(cli.str_t, "drive"),
                 cli.arg(cli.str_t, "type", expander=type_expand)],
                short = "set floppy parameters",
                cls = class_name,
                doc = """
Sets information in the CMOS about floppy drives. The <arg>drive</arg> is
either <tt>A</tt> (primary drive) or <tt>B</tt> (secondary drive), and type is
the maximal drive size (in kB or MB); 360, 720, 1.2, 1.44, 2.88. Setting
<arg>type</arg> to "none" indicates to the OS/BIOS that no drive is present.
Since both arguments are strings, quoting is sometimes necessary.""")

    def cmos_hd_cmd_instance(obj, drive, cylinders, heads, sectors_per_track):
        cmos_hd_cmd(obj, drive, cylinders, heads, sectors_per_track, get_rtc = get_rtc_func)

    cli.new_command("cmos-hd", cmos_hd_cmd_instance,
                [cli.arg(cli.str_t, "drive"),
                 cli.arg(cli.int_t, "cylinders"),
                 cli.arg(cli.int_t, "heads"),
                 cli.arg(cli.int_t, "sectors_per_track")],
                short = "set fixed disk parameters",
                cls = class_name,
                doc = """
Sets information in the CMOS about the primary and secondary hard disk where
<arg>drive</arg> is one of <tt>C</tt> <tt>D</tt>. The settings are
<arg>cylinders</arg>, <arg>heads</arg> and  <arg>sectors_per_track</arg>.""")

    def cmos_boot_dev_cmd_instance(obj, drive):
        cmos_boot_dev_cmd(obj, drive, get_rtc = get_rtc_func)

    cli.new_command("cmos-boot-dev", cmos_boot_dev_cmd_instance,
                [cli.arg(cli.str_t, "drive")],
                short = "set boot drive",
                cls = class_name,
                doc = """
Specifies boot device for the BIOS in the CMOS. Possible values for
<arg>drive</arg> are <tt>A</tt>, <tt>C</tt>, or <tt>CD-ROM</tt>, for floppy
boot, HD boot, and CD-ROM boot respectively. These options are only useful with
Simics provided BIOSes, and CD-ROM boot is only supported with Seabios.
Default is <tt>C</tt>.""")

    def cmos_info_cmd_instance(obj):
        cmos_info_cmd(obj, get_rtc = get_rtc_func)

    cli.new_command("cmos-info", cmos_info_cmd_instance,
                [],
                short = "print information about the CMOS area",
                cls = class_name,
                doc = """
Print detailed information about the CMOS information from the RTC device.""")
