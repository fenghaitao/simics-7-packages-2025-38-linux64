# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os
import re

import cli
import simics
import conf
import table
from checkpoint_info import update_checkpoint_info
from deprecation import DEPRECATED

from simics import (
    SIM_VERSION_6,

    Column_Key_Name,
    Table_Key_Columns,
)

from cli import (
    CliError,
    arg,
    command_return,
    command_verbose_return,
    filename_t,
    flag_t,
    int_t,
    new_command,
    obj_t,
    str_t,
    uint64_t,
)

from sim_commands import (
    binary_amount,
    get_memory_limit_data,
)

from mem_commands import check_file_exists

# Set persistent data of PHASE for object OBJNAME from attributes found
# in pre-conf object POBJ. Return True if all went well, False on error.
def set_persistent_obj_data(phase, objname, pobj):
    try:
        o = simics.SIM_get_object(objname)
    except simics.SimExc_General:
        print("Failed applying persistent state to object %s." % objname)
        print("Perhaps the file refers to some other configuration?")
        return False

    ok = True
    for (attr, val) in pobj.__dict__.items():
        if attr.startswith('__'):
            continue                    # not an attribute
        aa = simics.SIM_get_attribute_attributes(o.classname, attr)
        m = simics.Sim_Init_Phase_Mask
        if ((aa >> simics.Sim_Init_Phase_Shift) & m) == (phase & m):
            try:
                simics.SIM_set_attribute(o, attr, val)
            except simics.SimExc_General as ex:
                print("Failed setting %s.%s: %s" % (objname, attr, ex))
                ok = False
    return ok

def set_persistent_data(config, prefix):
    ok = True
    for phase in (-1, 0, 1):
        for (name, pobj) in config.items():
            if name != 'sim':
                objname = prefix + name
            else:
                objname = name
            ok &= set_persistent_obj_data(phase, objname, pobj)
    if not ok:
        raise cli.CliError("Failures when loading persistent state.")

# Run ACTION with DIR as temporary current working directory.
def with_cwd(dir, action):
    here = os.getcwd()
    try:
        os.chdir(dir)
        action()
    finally:
        os.chdir(here)

def image_save(image, filename, start, length, save_type_selection,
               overwrite, uncompressed):
    check_file_exists(filename, overwrite)

    if uncompressed:
        save_flags = simics.Sim_Save_Image_Uncompressed_Craff
    else: save_flags = 0
    (_, _, save_file_type) = save_type_selection
    save_flags |= (
        {"-save-raw": simics.Sim_Save_Image_Raw,
         "-save-vhdx": simics.Sim_Save_Image_VHDX}.get(save_file_type,0
                                                       ))  # 0 means craff file
    try:
        image.iface.image.save_to_file(filename, start, length, save_flags)
        return command_return("Image contents saved to %s file." % filename)
    except simics.SimExc_General as ex:
        raise CliError("Failed saving image to file: %s" % ex)


for (name, ifc) in [("save-image-contents", None), ("save", "image")]:
    # create one global and one namespace command doing the same thing
    if ifc:
        args = []
        see_also = ['save-image-contents', '<image>.save-diff-file']
        docstr = ""
    else:
        args = [arg(obj_t("image object", kind = "image"), "image")]
        see_also = ['<image>.save', '<image>.save-diff-file']
        docstr = " for the specified <arg>image</arg>"
    new_command(name, image_save,
                args + [arg(filename_t(), "filename"),
                        arg(uint64_t, "start-byte", "?", 0),
                        arg(uint64_t, "length", "?", 0),
                        arg((flag_t, flag_t, flag_t),
                            ("-save-craff", "-save-raw", "-save-vhdx"), "?",
                            (flag_t, 1, "-save-craff")),
                        arg(flag_t, "-overwrite"),
                        arg(flag_t, "-u")],
                type = ["Image", "Disks", "Configuration"],
                short = "save image to disk",
                see_also = see_also,
                iface = ifc,
                doc = f"""
Writes the image contents to <arg>filename</arg>{docstr} in the specified format.

If <arg>start-byte</arg> and/or <arg>length</arg> are given, they specify the
start offset address and number of bytes to write respectively; otherwise, the
whole image is copied.

If <tt>-save-craff</tt> is specified, data is saved in craff format,
using compression unless <tt>-u</tt> is specified. If
<tt>-save-raw</tt> is specified, data is saved in raw format, which is
also the default option. If <tt>-save-vhdx</tt> is specified,
data is saved in VHDX format.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.
""")

def image_save_diff(image, filename, overwrite, uncompressed):
    check_file_exists(filename, overwrite)
    if uncompressed:
        save_flags = simics.Sim_Save_Image_Uncompressed_Craff
    else: save_flags = 0
    try:
        image.iface.image.save_diff(filename, save_flags)
    except simics.SimExc_General as ex:
        raise CliError("Failed saving image diff to file: %s" % ex)

    if not os.path.exists(filename):
        print("%s has no changes - no file created." % image.name)

for (name, ifc) in [("save-image-diff", None), ("save-diff-file", "image")]:
    # create one global and one namespace command doing the same thing
    if ifc:
        args = []
        see_also = ["save-image-diff", "<image>.save", "save-image-contents"]
        docstr = "image"
    else:
        args = [arg(obj_t("image object", kind = "image"), "image")]
        see_also = ["<image>.save-diff-file", "save-image-contents",
                    "<image>.save"]
        docstr = "specified <arg>image</arg>"
    new_command(name, image_save_diff,
                args + [arg(filename_t(), "filename"),
                        arg(flag_t, "-overwrite"),
                        arg(flag_t, "-u")],
                type = ["Image", "Disks", "Configuration"],
                short = "save changes since last checkpoint",
                see_also = see_also,
                iface = ifc,
                doc = f"""
Writes changes to the {docstr} since the last checkpoint to
<arg>filename</arg>.

No file is created if there are no changes to the image.

By default the file is written in compressed craff format, unless <tt>-u</tt>
is specified.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.
""")

def image_add_partial_diff(image, filename, start, size, force, replace, rw):
    if not (replace or force) and image.dirty:
        raise CliError("Image '%s' contains unsaved changes."
                       % image.name)
    if replace:
        files = []
    else:
        files = list(image.files)
    files += [[filename, "rw" if rw else "ro", start, size]]
    try:
        image.files = files
    except Exception as ex:
        raise CliError("Error adding %s to %s: %s"
                       % (filename, image.name, ex))

def image_add_diff(image, filename, replace, rw, force):
    if replace:
        DEPRECATED(SIM_VERSION_6,
                   "The -replace flag to add-diff-file is deprecated.",
                   "Use the clear-files command instead.")
    map_size = image.size
    actual_file = simics.SIM_lookup_file(filename)
    if actual_file:
        filesize = simics.VT_logical_file_size(actual_file)
        if filesize < image.size:
            simics.SIM_log_info(
                1, image, 0,
                "Warning: adding file %s of size %d to image of size %d"
                % (actual_file, filesize, image.size))
            map_size = filesize
    image_add_partial_diff(image, filename, 0, map_size, force, replace, rw)

new_command("add-diff-file", image_add_diff,
            [arg(filename_t(keep_simics_ref=True), "filename"),
             arg(flag_t, "-replace"),
             arg(flag_t, "-rw"),
             arg(flag_t, "-force")],
            type = ["Image", "Disks", "Configuration"],
            short = "add a diff file to the image",
            see_also = ['<image>.add-partial-diff-file',
                        '<image>.clear-files',
                        '<image>.save-diff-file'],
            cls = "image",
            doc = """
Adds a diff file, <arg>filename</arg>, to the list of files for an image. The
diff file was typically created with <cmd class="image">save-diff-file</cmd>,
or by a saved configuration.

The file can be treated as writable instead of read-only using the
<tt>-rw</tt> flag. The <cmd class="image">clear-files</cmd> command should be
used instead of the deprecated <tt>-replace</tt> flag.

If any unsaved changes are found in the image object, the command will
fail. Such changes can be discarded by using the <tt>-force</tt> flag, or
first saved using the <cmd class="image">save-diff-file</cmd> command.""")

# Is "descendant" a descendant of "ancestor" in the object hierarchy?
def is_descendant(ancestor, descendant):
    # Every object is a descendant of the root
    if ancestor is None:
        return True
    while (descendant is not None and ancestor != descendant):
        descendant = simics.SIM_object_parent(descendant)
    # Either we found the ancestor or the root
    return descendant is not None

def load_existing_rw_state(imgs, path):
    assert os.path.isdir(path)

    # Proceed similarly as in load-persistent-state
    try:
        config = simics.VT_get_configuration(path)
    except simics.SimExc_General as ex:
        raise CliError(f"Failed opening persistent state file: {ex}")

    simics.VT_set_restoring_state(True)
    try:
        with_cwd(path, lambda: set_persistent_data(config, ""))

        # Copy all image file lists, to allow rollback
        img_files = {img: list(img.files) for img in imgs}

        # Mark state files as R/W state
        # This will throw away any dirty data, which is expected.
        try:
            for img in imgs:
                files = img_files[img]
                if not files:
                    raise simics.SimExc_IllegalValue(
                        f"{img.name} has no backing files")
                files[-1][1] = "rw"
                img.files = files
        except simics.SimExc_IllegalValue as ex:
            # Revert to read-only => behave as load-persistent-state
            for img in imgs:
                files = img_files[img]
                if not files:
                    continue
                files[-1][1] = "ro"
                img.files = files
            raise CliError("Could not enable R/W state. State has been loaded"
                           f" as read-only: {ex}")
    finally:
        simics.VT_set_restoring_state(False)

def enable_initial_rw_state(imgs, path, root, comment):
    old_force_diff = conf.classes.image.force_diff
    flags = simics.Sim_Save_Image_Uncompressed_Craff

    try:
        conf.classes.image.force_diff = True

        # Save existing state
        simics.SIM_write_persistent_state(path, root, flags)
        update_checkpoint_info(path, {'comment' : comment})

        # Mark created diffs as R/W
        for img in imgs:
            files = list(img.files)
            files[-1][1] = "rw"
            img.files = files
    except Exception as ex:
        raise CliError(f"Error enabling persistent state: {ex}")
    finally:
        conf.classes.image.force_diff = old_force_diff


def enable_rw_state(path, root, new_only, comment):
    cli.assert_not_running()

    imgs = {img for img in simics.SIM_object_iterator_for_class('image')
            if (img.iface.checkpoint.has_persistent_data()
                and is_descendant(root, img))}

    if not imgs:
        raise CliError("No images with persistent data in the configuration"
                       + (f" rooted at {root}" if root else ""))

    for img in imgs:
        if "rw" in {read_only for (_, read_only, _, _, _) in img.files}:
            raise CliError(f"Image '{img.name}' already has a writable file")

    p = simics.SIM_native_path(path)
    if new_only and os.path.exists(p):
        raise CliError(f"The path '{p}' already exists.")
    if os.path.exists(p) and not os.path.isdir(p):
        raise CliError(f"The path '{p}' must be a directory.")

    if os.path.exists(p):
        if comment:
            simics.SIM_log_warning(
                conf.sim, 0, 'enable-writable-persistent-state:'
                f' ignoring comment since state directory "{p}" exists')
        load_existing_rw_state(imgs, p)
        return command_return('Enabled existing writable'
                              f' persistent state at "{p}".')
    else:
        enable_initial_rw_state(imgs, p, root, comment)
        return command_return('Enabled new writable'
                              f' persistent state at "{p}".')

new_command("enable-writable-persistent-state", enable_rw_state,
            [arg(filename_t(checkpoint=True), "dir"),
             arg(obj_t("object"), "root", "?", None),
             arg(flag_t, "-new"),
             arg(str_t, "comment", "?", None)],
            type = ["Image", "Memory", "Disks", "Configuration"],
            short = "create/load a R/W persistent state",
            see_also = ['save-persistent-state',
                        'load-persistent-state',
                        'list-persistent-images'],
            doc = """
Enables a writable persistent simulator state in the directory
<arg>dir</arg>.  Persistent data typically includes disk images, NVRAM
and flash memory contents and clock settings, i.e. data that survive
reboots. The persistent state is saved as a standard Simics
configuration.

The persistent state will contain persistent data from objects in the
hierarchy rooted at <arg>root</arg>, or all persistent data if that
argument is NIL.

To use this command, no image is allowed to have a writable file already.

If the directory exists, it must contain a saved persistent state
previously created by this command, whose objects match the
configuration under <arg>root</arg>, and this state will be loaded and
used as writable state. Otherwise a new state will be created.

If <tt>-new</tt> is specified and the directory <arg>dir</arg> exists,
an error will be raised.

If a new state is created, a description can be added to the
persistent state, using the <arg>comment</arg> argument. The comment
is saved in the <file>info</file> file in the persistent state directory.
""")

def image_add_partial_diff_helper(image, filename, start, size, force):
    image_add_partial_diff(image, filename, start, size, force, False, False)

new_command("add-partial-diff-file", image_add_partial_diff_helper,
            [ arg(filename_t(keep_simics_ref=True), "filename"),
              arg(uint64_t, "start"),
              arg(uint64_t, "size", "?", 0),
              arg(flag_t, "-force")],
            type = ["Image", "Disks", "Configuration"],
            short = "add a partial diff file to the image",
            see_also = ['<image>.add-diff-file', '<image>.save-diff-file'],
            cls = "image",
            doc = """
Adds a partial diff file, <arg>filename</arg>, to the list of files for an
image. The diff file was typically created with the
<cmd class="image">save-diff-file</cmd> command, by one of the
dump-*-partition commands, or by a saved configuration. The <arg>start</arg>
and <arg>size</arg> arguments specify the location within the image. If
<arg>size</arg> is left out, the (virtual) size of the file is used.

If any unsaved changes are found in the image object, the command will
fail. Such changes can be discarded by using the <tt>-force</tt> flag, or
first saved using the <cmd class="image">save-diff-file</cmd> command.""")

def image_clear_files(image):
    try:
        image.files = []
    except Exception as ex:
        raise CliError("Error clearing files from image %s: %s"
                       % (image.name, ex))

new_command("clear-files", image_clear_files,
            [],
            type = ["Image", "Disks", "Configuration"],
            short = "clear the list of files for an image",
            see_also = ['<image>.add-diff-file',
                        '<image>.list-files'],
            cls = "image",
            doc = """
Clears the list of files that represent the contents of a image. This is useful
when replacing the contents of a disk before starting the simulation without
having to modify the initial machine configuration.

The command will discard any unsaved changes to the image. Such changes can
first be saved using the <cmd class="image">save-diff-file</cmd> command.""")

def expand_checkpoint_path(f):
    # replace %0% style placeholders with actual checkpoint path
    m = re.match(r"^%([0-9]+)%([/\\])", f)
    if m:
        index = int(m.group(1))
        dirsep = m.group(2)
        if index < len(conf.sim.checkpoint_path):
            cpath = conf.sim.checkpoint_path[index]
            f = os.path.join(cpath, f.split(dirsep, 1)[1])
        else:
            f = f.split(dirsep, 1)[1]
    return f

def image_list_files(image, verbose):
    files = []
    for file_info in image.files:
        (f, acc, s, z, o) = file_info[0:5]
        if verbose:
            f = expand_checkpoint_path(f)
        else:
            f = os.path.basename(f)
        files.append([f, acc, s, z, o])

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in
               ["File", "Access", "Start", "Size", "Offset"]])]
    tbl = table.Table(props, files)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, files)

new_command("list-files", image_list_files,
            [arg(flag_t, '-v')],
            type = ["Image", "Disks", "Configuration"],
            short = "list files representing the contents of an image",
            see_also = ['<image>.add-diff-file',
                        '<image>.clear-files'],
            cls = "image",
            doc = """
Prints a list of all files that represent the contents of a image. In addition
to the file name, the output also includes the start offset for the file within
the image, the virtual size of the file to be mapped, and the start offset
within the file (usually zero). The <tt>-v</tt> flag turns on verbose output
where the full path to files are included.

When used in an expression, the file information is returned as a list of
lists.

If file are overlapping, the contents of the last file in the list takes
precedence. Note that certain file formats support holes.
""")

def set_memory_limit_cmd(limit, swapdir):
    if limit == None and not swapdir:
        (lim, sd, _) = get_memory_limit_data()
        print("Image memory", lim)
        print("Swap directory:", sd)
        return

    if limit != None:
        if limit < 0:
            raise CliError("Illegal memory limit.")
        elif limit > 0:
            limit = limit << 20
            if limit > conf.sim.host_phys_mem:
                print("Warning: Limit larger than the amount of physical memory.")
                return
            conf.classes.image.memory_limit = limit
            print("Image memory limited to", binary_amount(limit))
        elif limit == 0:
            conf.classes.image.memory_limit = limit
            print("Image memory not limited.")

    if swapdir:
        try:
            conf.prefs.swap_dir = swapdir
        except simics.SimExc_IllegalValue as ex:
            raise CliError("Could not set swap directory: %s" % ex)
        # swap dir may be mangled, so print out the result
        print("Swap dir set to", conf.prefs.swap_dir)

new_command("set-image-memory-limit", set_memory_limit_cmd,
            [arg(int_t, "limit", "?", None),
             arg(filename_t(dirs=True, exist=True), "swapdir", "?", None)],
            type = ["Image"],
            short = "limit image memory usage",
            doc = """
Limits the in-memory footprint of all image objects to <arg>limit</arg>
megabytes. This only limits the memory consumed by image pages in memory.
While this is typically a very large part of Simics's memory usage, other
data structures are not limited by this command.

If <arg>limit</arg> is zero, the memory limit is removed.
If <arg>swapdir</arg> is specified, it indicates a directory to use for
swap files. If no argument is given, the current setting is
displayed.

Simics sets a default memory limit at startup that depends on the amount of
memory on the host system, generally about two-thirds.
""")

def default_memory_limit():
    total = min(conf.sim.host_phys_mem, conf.sim.host_virt_mem)

    # remove 64MB for system
    total -= 0x4000000

    # lowest limit is 256MB, or the amount of memory in the system
    min_total = min(total, 0x10000000)

    # leave some memory for non-image stuff
    return int(max(total * 0.7, min_total)) & ~0xfffff

conf.classes.image.memory_limit = default_memory_limit()
