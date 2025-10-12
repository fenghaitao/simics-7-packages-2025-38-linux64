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

pc_partition_types = { 0x00 : "unused",
                       0x01 : "FAT12",
                       0x04 : "FAT16",
                       0x05 : "Extended (CHS)",
                       0x06 : "FAT16B",
                       0x07 : "NTFS/exFAT",
                       0x0b : "FAT32 (CHS)",
                       0x0c : "FAT32 (LBA)",
                       0x0e : "FAT16 (LBA)",
                       0x0f : "Extended (LBA)",
                       0x82 : "Linux swap",
                       0x83 : "Linux native",
                       0x85 : "Linux extended",
                       0x8e : "Linux LVM",
                       0xa5 : "FreeBSD",
                       0xa6 : "OpenBSD",
                       0xa8 : "Apple UFS",
                       0xa9 : "NetBSD",
                       0xab : "Apple boot",
                       0xaf : "Apple HFS",
                       0xef : "EFI system" }

def build_32bit(a, b, c, d):
    return (a << 0) | (b << 8) | (c << 16) | (d << 24)

class part_info:
    pass

def read_mbr_partition(obj, i):
    sector = list(obj.image.iface.image.get(0, 512))
    data = sector[0x1be + 16 * i : 0x1be + 16 * i + 16]
    pi = part_info()
    pi.bootable = data[0]
    pi.type = data[4]
    pi.start_c = ((data[2] >> 6) << 8) | data[3]
    pi.start_h = data[1]
    pi.start_s = data[2] & 0x3f
    pi.end_c = ((data[6] >> 6) << 8) | data[7]
    pi.end_h = data[5]
    pi.end_s = data[6] & 0x3f
    pi.lba = build_32bit(data[8], data[9], data[10], data[11])
    pi.size = build_32bit(data[12], data[13], data[14], data[15])
    return pi

def print_partition_table_cmd(obj):
    print("Partition table for %s:" % obj.name)
    print("Id BI  St  C/  H/ S   E  C/  H/ S  LBA ----  Size ---  Offset -----  Type")
    for i in range(4):
        try:
            pi = read_mbr_partition(obj, i)
        except simics.SimExc_General as ex:
            print(f"The partition table seems corrupt: {ex}")
            return
        type_name = pc_partition_types.get(pi.type, "0x%x" % pi.type)
        print(" %d %02x   %4d/%3d/%2d   %4d/%3d/%2d  %8u  %8u  %12u  %s" % (
            i, pi.bootable,
            pi.start_c, pi.start_h, pi.start_s,
            pi.end_c, pi.end_h, pi.end_s,
            pi.lba, pi.size, pi.lba * 512,
            type_name))

def save_mbr_partition(obj, i, filename, save_type):
    if i > 3:
        raise cli.CliError("Partition %d out of range (0 .. 3 allowed)." % i)
    pi = read_mbr_partition(obj, i)
    from sim_commands import image_save
    image_save(obj.image, filename, pi.lba * 512, pi.size * 512, save_type,
               False, False)

def create_pc_partition_table_commands(class_name):
    cli.new_command("print-partition-table", print_partition_table_cmd,
                [],
                type = ["Disks"],
                short = "print the partition table",
                cls = class_name,
                see_also = ['<%s>.save-mbr-partition' % class_name],
                doc = """
Print the partition table for a disk. MBR is the only supported format.
""")

    cli.new_command("save-mbr-partition", save_mbr_partition,
                [cli.arg(cli.uint_t, "partition"),
                 cli.arg(cli.filename_t(), "filename"),
                 cli.arg((cli.flag_t, cli.flag_t), ("-save-craff", "-save-raw"), "?",
                         (cli.flag_t, 0, "-save-raw")) ],
                type = ["Disks"],
                short = "save an MBR partition to a file",
                see_also = ['<image>.save',
                            '<%s>.print-partition-table' % class_name],
                cls = class_name,
            doc = """
Writes a selected MBR <arg>partition</arg> to the file <arg>filename</arg>. If
<tt>-save-craff</tt> is specified, data is saved in craff format. If
<tt>-save-raw</tt> is specified, data is saved in raw format, which is also the
default option.""")
