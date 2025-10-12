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


from cli import (new_command, arg, filename_t, flag_t, uint64_t)
from simics import SIM_get_attribute
import sim_commands

#
# -------------------- info --------------------
#

def info_cmd(obj):
    dev_name = obj.classname
    print("%s information" % dev_name)
    print("=====================")
    try:
        geom = SIM_get_attribute(obj, "geometry")

    except Exception as msg:
        print("Error getting info from %s: %s" % (dev_name, msg))
        return

    print("                Cylinders: %5d" % geom[0])
    print("                   Heads : %5d" % geom[1])
    print("       Sectors per track : %5d" % geom[2])
    print()

    print("        Sectors read     : %d  ( = %d bytes)" % (obj.sectors_read, obj.sectors_read * 512))
    print("        Sectors written  : %d  ( = %d bytes)" % (obj.sectors_written, obj.sectors_written * 512))
    print()

new_command("info", info_cmd,
            [],
            short = "information about current state of the SCSI disk",
            cls = "simple-scsi-disk",
            doc = """
Print information about the state of the simple SCSI disk.<br/>
""")

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
            see_also = ['<simple-scsi-disk>.add-diff-file', '<image>.save-diff-file'],
            cls = "simple-scsi-disk",
            doc = """
Writes changes to the image as a diff file <arg>filename</arg> in the craff
file format.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.

This is basically the same command as <cmd class="image">save-diff-file</cmd>.
""")

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
            see_also = ['<simple-scsi-disk>.save-diff-file', '<image>.add-diff-file'],
            cls = "simple-scsi-disk",
            doc = """
Adds a diff file <arg>filename</arg> to the list of files for an disk. This is
basically the same command as <cmd class="image">add-diff-file</cmd>.

The diff file was typically created with the <cmd
class="simple-scsi-disk">save-diff-file</cmd> command, or by a saved
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
            see_also = ['<simple-scsi-disk>.save-diff-file',
                        '<image>.add-diff-file',
                        '<image>.add-partial-diff-file'],
            cls = "simple-scsi-disk",
            doc = """
Adds a partial diff file, <arg>filename</arg>, to the list of files for a
disk. This is basically the same command as <cmd
class="image">add-partial-diff-file</cmd>.

The diff file was typically created with the <cmd
class="simple-scsi-disk">save-diff-file</cmd> command, or by a saved
configuration. The <arg>start</arg> and <arg>size</arg> arguments specify the
location within the image. If <arg>size</arg> is left out, the (virtual) size
of the file is used.

If any unsaved changes are found in the image object, the command will
fail. Such changes can be discarded by using the <tt>-force</tt> flag, or
first saved using the <cmd class="image">save-diff-file</cmd> command.
""")

try:
    import sun_vtoc_commands
except ImportError:
    pass
else:
    sun_vtoc_commands.create_sun_vtoc_commands("simple-scsi-disk")

try:
    import pc_disk_commands
except ImportError:
    pass
else:
    pc_disk_commands.create_pc_partition_table_commands("simple-scsi-disk")
