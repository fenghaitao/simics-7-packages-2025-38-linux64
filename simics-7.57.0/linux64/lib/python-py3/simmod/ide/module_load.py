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
    filename_t,
    flag_t,
    new_command,
    new_info_command,
    new_status_command,
    obj_t,
    uint64_t,
    uint_t,
    )
from simics import *

#
# -------------------- insert --------------------
#

def insert_cmd(obj, medium, cd, dvd):
    if cd and dvd:
        raise CliError("The -dvd and -cd switches are exclusive.")
    if (not cd) and (not dvd):
        cd = 1
    try:
        obj.cd_media = medium
        if cd:
            obj.current_profile = "CD-ROM"
        if dvd:
            obj.current_profile = "DVD-ROM"
        print("Inserting media '%s' in CD-ROM drive" % medium.name)
    except Exception as msg:
        print("Error inserting media: %s" % msg)

new_command("insert", insert_cmd,
            [arg(obj_t("object", "cdrom_media"), "media"),
             arg(flag_t, "-cd"),
             arg(flag_t, "-dvd")],
            type  = ["Disks"],
            short = "insert media in CD-ROM drive",
            cls = "ide-cdrom",
            doc = """
Insert a media in the CD-ROM drive. The <arg>media</arg> is the name of a
CD-ROM media object, e.g., a cdrom-image. Use the <tt>-cd</tt> flag to indicate
that the media is a CD-ROM, or the <tt>-dvd</tt> flag for DVD-ROM. CD-ROM is
the default choice if none of the flags are given.""")

#
# -------------------- eject --------------------
#

def eject_cmd(obj):
    try:
        obj.cd_media = None
        obj.current_profile = None
        print("Ejecting media from CD-ROM drive")
    except Exception as msg:
        print("Error ejecting media: %s" % msg)

new_command("eject", eject_cmd,
            [],
            type  = ["Disks"],
            short = "eject media from CD-ROM drive",
            cls = "ide-cdrom",
            doc = """
Eject a media from the CD-ROM drive. The media must have been
previously inserted with the 'insert' command.
""")

def get_info(obj):
    if obj.classname == "ide-cdrom":
        if obj.cd_media:
            media = [("Connected media", obj.cd_media.name),
                     ("Media type", obj.current_profile)]
        else:
            media = [("Connected media", "empty")]
    else:
        media = [("Cylinders", "%5d" % obj.disk_cylinders),
                 ("Heads", "%5d" % obj.disk_heads),
                 ("Sectors per track", "%5d" % obj.disk_sectors_per_track),
                 ("Total sector count", "%5d" % obj.disk_sectors)]

    return [(None,
             [("Model ID", obj.model_id),
              ("Firmware ID", obj.firmware_id),
              ("Serial Number", obj.serial_number)]
             + media)]

new_info_command("ide-cdrom", get_info)
new_info_command("ide-disk", get_info)
# No status commands, since there isn't much status to show

#
# -------------- default-translation ------------
#
#disk_cylinders disk_heads disk_sectors_per_track
def translation_cmd(obj, c, h, s):

    if c == h == s == -1:
        str = "Current"
    else:
        str = "New"

    try:
        if c == -1:
            c = SIM_get_attribute(obj, "disk_cylinders")
        else:
            SIM_set_attribute(obj, "disk_cylinders", c)
        if h == -1:
            h = SIM_get_attribute(obj, "disk_heads")
        else:
            SIM_set_attribute(obj, "disk_heads", h)
        if s == -1:
            s = SIM_get_attribute(obj, "disk_sectors_per_track")
        else:
            SIM_set_attribute(obj, "disk_sectors_per_track", s)
    except Exception as msg:
        print("Error setting/getting disk information: %s" % (msg,))

    print("%s translation: C=%d H=%d S=%d" % (str, c, h, s))


new_command("default-translation", translation_cmd,
            [arg(uint_t, "C", "?", -1),
             arg(uint_t, "H", "?", -1),
             arg(uint_t, "S", "?", -1)],
            type  = ["Disks"],
            short = "get or set the default CHS translation",
            cls = "ide-disk",
            doc = """
Set the default CHS translation of a disk using <arg>C</arg>, <arg>H</arg>
and <arg>S</arg> or print the current one if no arguments are given.""")

import os
import sim_commands

#
# -------------------- save-diff-file ----------------
#

def image_save_diff(obj, file, overwrite):
    sim_commands.image_save_diff(obj.image, file, overwrite, False)

new_command("save-diff-file", image_save_diff,
            [arg(filename_t(), "filename"),
             arg(flag_t, "-overwrite")],
            type = ["Disks"],
            short = "save diff file to disk",
            see_also = ['<ide-disk>.add-diff-file', '<image>.save-diff-file'],
            cls = "ide-disk",
            doc = """
Writes changes to the image as the diff file <arg>filename</arg> in the craff
file format.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.

This is basically the same command as
<cmd class="image">save-diff-file</cmd>.""")

#
# -------------------- add-diff-file ----------------
#

def image_add_diff(obj, file, replace, rw, force):
    sim_commands.image_add_diff(obj.image, file, replace, rw, force)

new_command("add-diff-file", image_add_diff,
            [arg(filename_t(keep_simics_ref=True), "filename"),
             arg(flag_t, "-replace"),
             arg(flag_t, "-rw"),
             arg(flag_t, "-force")],
            type = ["Disks"],
            short = "add a diff file to the image",
            see_also = ['<ide-disk>.save-diff-file', '<image>.add-diff-file'],
            cls = "ide-disk",
            doc = """
Adds the diff file <arg>filename</arg> to the list of files for a disk. This
is basically the same command as <cmd class="image">add-diff-file</cmd>.

The diff file was typically created with the <cmd
class="ide-disk">save-diff-file</cmd> command, or by a saved
configuration. The file can be made writable instead of read-only using the
<tt>-rw</tt> flag. The <cmd class="image">clear-files</cmd> command should be
used instead of the deprecated <tt>-replace</tt> flag.

If any unsaved changes are found in the image object, the command will
fail. Such changes can be discarded by using the <tt>-force</tt> flag, or
first saved using the <cmd class="image">save-diff-file</cmd> command.
""")

#
# -------------------- add-partial-diff-file ----------------
#

def image_add_partial_diff(obj, file, start, size, force):
    sim_commands.image_add_partial_diff(obj.image, file, start, size,
                                        force, False, False)

new_command("add-partial-diff-file", image_add_partial_diff,
            [arg(filename_t(keep_simics_ref=True), "filename"),
             arg(uint64_t, "start"),
             arg(uint64_t, "size", "?", 0),
             arg(flag_t, "-force")],
            type = ["Disks"],
            short = "add a partial diff file to the image",
            alias = 'add-diff-partial-file', # for compatibility with old cmd
            see_also = ['<ide-disk>.save-diff-file',
                        '<image>.add-diff-file',
                        '<image>.add-partial-diff-file'],
            cls = "ide-disk",
            doc = """
Adds a partial diff file, <arg>filename</arg>, to the list of files for a
disk. This is basically the same command as <cmd
class="image">add-partial-diff-file</cmd>.

The diff file was typically created with the <cmd
class="ide-disk">save-diff-file</cmd> command, or by a saved
configuration. The <arg>start</arg> and <arg>size</arg> arguments specify the
location within the image. If <arg>size</arg> is left out, the (virtual) size
of the file is used.

If any unsaved changes are found in the image object, the command will
fail. Such changes can be discarded by using the <tt>-force</tt> flag, or
first saved using the <cmd class="image">save-diff-file</cmd> command.
""")


#
# -------------------- ide info commands ----------------
#

def ide_get_info(obj):
    return [ (None,
              [ ("IRQ device", obj.irq_dev),
                ("IRQ number", obj.irq_level),
                ("Interrupt delay", obj.interrupt_delay),
                ("Model DMA delay", obj.model_dma_delay),
                ("Master", obj.master),
                ("Slave", obj.slave),
                ("Bus master DMA", obj.bus_master_dma) ] ) ]

def ide_get_status(obj):
    return [ (None,
              [ ("Selected drive", obj.selected_drive),
                ("LBA mode", obj.lba_mode),
                ("Interrupt request status", obj.interrupt_pin),
                ("DMA ready", obj.dma_ready) ] ) ]

new_info_command("ide", ide_get_info)
new_status_command("ide", ide_get_status)


try:
    import pc_disk_commands
except ImportError:
    pass
else:
    pc_disk_commands.create_pc_partition_table_commands("ide-disk")

try:
    import sun_vtoc_commands
except ImportError:
    pass
else:
    sun_vtoc_commands.create_sun_vtoc_commands("ide-disk")
