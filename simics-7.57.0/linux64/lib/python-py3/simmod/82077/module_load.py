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
    str_t,
    )
from simics import *
import os

disk_types = { "320" : [40,  8, 2],
               "360" : [40,  9, 2],
               "720" : [80,  9, 2],
               "1.2" : [80, 15, 2],
              "1.44" : [80, 18, 2],
              "2.88" : [80, 36, 2]}

def floppy_drive_get_info(obj):
    return ( None )

def floppy_drive_get_status(obj):
    floppy_size = [obj.tracks, obj.sectors_per_track, obj.heads]
    try:
        idx = list(disk_types.values()).index(floppy_size)
        floppy_type = list(disk_types.keys())[idx]
    except:
        floppy_type = "Unknown"

    drive = ("Drive",
             [ ("Busy", obj.drive_busy),
               ("Seek in progress", obj.seek_in_progress),
               ("Disk changed", obj.disk_changed),
               ("Motor", "on" if obj.motor_on else "off"),
               ("Data rate", obj.data_rate),
               ("Current head", obj.cur_head),
               ("Current sector", obj.cur_sector) ] )
    if obj.image:
        floppy = ("Floppy",
                  [ ("Floppy type", floppy_type),
                    ("Write protect", obj.write_protect),
                    ("Tracks", obj.tracks),
                    ("Sectors per track", obj.sectors_per_track),
                    ("Heads", obj.heads),
                    ("Image object", obj.image.name) ] )
    else:
        floppy = ("Floppy",
                  [ ("No floppy", "") ])
    return [ drive, floppy ]


new_info_command('floppy-drive', floppy_drive_get_info)
new_status_command('floppy-drive', floppy_drive_get_status)


def i82077_get_info(obj):
    return [ (None,
              [ ("IRQ device", obj.irq_dev),
                ("IRQ number", obj.irq_level),
                ("DMA device", obj.dma_dev),
                ("DMA channel", obj.dma_channel),
                ("Floppy drives", obj.drives) ] ) ]

def i82077_get_status(obj):
    return [ (None,
              [ ("Enabled", "yes" if obj.enabled else "no"),
                ("DMA enabled", "yes" if obj.dma_enabled else "no"),
                ("FIFO enabled", "yes" if obj.fifo_enabled else "no"),
                ("Poll enabled", "yes" if obj.poll_enabled else "no"),
                ("State", ["idle", "command", "execute", "result"][obj.state]),
                ("Step rate", obj.step_rate),
                ("Selected drive", obj.drive_select),
                ("Command busy", obj.command_busy),
                ("Poll change", obj.poll_change),
                ("Current command", "0x%x" % obj.cmd_id),
                ("Implied seek", obj.implied_seek),
                ("ST0 register", obj.st0),
                ("ST1 register", obj.st1),
                ("ST2 register", obj.st2) ] ) ]


new_info_command('i82077', i82077_get_info)
new_status_command('i82077', i82077_get_status)

#
# -------------------- insert-floppy --------------------
#

floppy_count = 0

def insert_floppy_cmd(obj, drive, floppy_file, rw, size):
    global floppy_count
    drive = drive.upper()
    if not drive in ('A', 'B'):
        raise CliError("Incorrect drive-letter, use one of A and B")
    if ((drive == 'A' and len(obj.drives) < 1)
        or (drive == 'B' and len(obj.drives) < 2)):
        raise CliError("No drive '%s' connected to controller %s. "
                       "Cannot insert floppy." % (drive, obj.name))
    try:
        disk_size = disk_types[size]
    except:
        raise CliError("Unknown disk size %s." % size)
    if drive == 'A':
        fd = obj.drives[0]
    else:
        fd = obj.drives[1]
    if fd.image:
        raise CliError("Floppy already inserted into drive %s." % drive)
    fd.disk_changed = 1
    fd.tracks = disk_size[0]
    fd.sectors_per_track = disk_size[1]
    fd.heads = disk_size[2]
    # simply replace the old image object
    # make sure we use a unique name (e.g. after a checkpoint)
    unique = 0
    while not unique:
        image_name = 'fd_image_%s_%d' % (drive, floppy_count)
        floppy_count += 1
        try:
            SIM_get_object(image_name)
        except:
            unique = 1
    im_size = disk_size[0] * disk_size[1] * disk_size[2] * 512
    SIM_create_object('image', image_name,
                       [['queue', fd.queue], ['size', im_size]])
    fd.image = SIM_get_object(image_name)

    filesize = os.stat(floppy_file)[6]
    if filesize == 0:
        filesize = fd.image.size
        print("Image %s reported zero size, assuming special file." % (
            floppy_file))
    rw_str = 'rw' if rw == 1 else 'ro'
    try:
        fd.image.files = [[floppy_file, rw_str, 0, filesize]]
    except SimExc_IllegalValue as ex:
        raise CliError(ex)
    print("Floppy inserted in drive '%s:'. (File %s)." % (drive, floppy_file))
    if size != '1.44':
        print("Remember to set the floppy size in the CMOS as well.")

new_command("insert-floppy", insert_floppy_cmd,
            [arg(str_t, "drive-letter"),
             arg(filename_t(exist = 1, simpath = 1), "floppy-image"),
             arg(flag_t, "-rw"),
             arg(str_t, "size", "?", "1.44")],
            short = "insert floppy in drive",
            cls = "i82077",
            doc = """
Insert the file <arg>floppy-image</arg> as a floppy in the disk drive
specified by <arg>drive-letter</arg>. For floppies with a different size than
1.44 MB, the <arg>size</arg> argument must be supplied.

The <tt>-rw</tt> flag uses <arg>floppy-image</arg> in read-write mode, meaning
that no save or save-diff-file command to the associated image object need to
be used in order to save data written by the target software.""")

def eject_floppy_cmd(obj, drive):
    drive = drive.upper()
    if not drive in ('A', 'B'):
        raise CliError("Incorrect drive-letter, use one of A and B")
    if ((drive == 'A' and len(obj.drives) < 1)
        or (drive == 'B' and len(obj.drives) < 2)):
        raise CliError("No drive '%s' connected to controller %s. "
                       "Cannot insert floppy." % (drive, obj.name))
    if drive == 'A':
        fd = obj.drives[0]
    else:
        fd = obj.drives[1]
    if fd.image == None:
        raise CliError("No floppy in drive %s." % drive)
    fd.disk_changed = 1
    fd.image = None
    print("Floppy ejected from drive '%s:'." % (drive))

new_command("eject-floppy", eject_floppy_cmd,
            [arg(str_t, "drive-letter")],
            short = "eject floppy",
            cls = "i82077",
            doc = """
Eject the media from the disk drive specified by <arg>drive-letter</arg>.
""")
