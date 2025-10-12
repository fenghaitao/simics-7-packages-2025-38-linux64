# © 2016 Intel Corporation
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
import mmap
import re
import conf
import simics
from simmod.os_awareness import framework
import cli
import table
from simicsutils.internal import ensure_text
from . import uefi_fw_tracker_comp as composition
composition.uefi_fw_tracker_comp.register()

def get_uefi_fw_tracker_status(tracker):
    return [(None, [("Enabled", tracker.enabled)])]

def get_uefi_fw_tracker_info(tracker):
    return [(None, [("Parent", tracker.parent)])]

def get_uefi_fw_mapper_status(mapper):
    return [(None, [("Enabled", mapper.enabled)])]

def get_uefi_fw_mapper_info(mapper):
    return [(None, [("Parent", mapper.parent)])]

def read_next_element(content, pos, start_marker, end_marker):
    start_pos = content.find(start_marker, pos)
    if start_pos == -1:
        return (False, None)
    start_pos += len(start_marker)

    end_pos = content.find(end_marker, start_pos)
    if end_pos == -1:
        return (False, None)

    cur_pos = end_pos + len(end_marker)

    try:
        return (True, (cur_pos, ensure_text(content[start_pos: end_pos])))
    except UnicodeError as e:
        raise cli.CliError(str(e))

def next_line(content, pos):
    """Returns a tuple with (ok, npos) where 'ok' is True and 'npos' points
    to the character after the next line-break after 'pos' if such can be found,
    otherwise (False, None)."""
    eol_pos = content.find(b'\n', pos)
    if eol_pos == -1:
        return (False, None)
    next_line_pos = eol_pos + 1
    if next_line_pos == content.size():
        return (False, None)
    return (True, next_line_pos)

def is_empty_line(content, pos):
    """Returns true if the content on 'pos' contains DOS or Linux line break."""
    if chr(content[pos]) == '\n':
        return True
    if pos + 1 < content.size():
        return ("".join(chr(c) for c in content[pos:pos + 2])) == '\r\n'
    return False

def read_base_addr(content, pos):
    (ok, val) = read_next_element(
        content, pos, b"(Fixed Flash Address, BaseAddress=", b",")
    if not ok:
        return (False, None, None)
    pos = val[0]
    base_addr = int(val[1], 16)
    return (True, pos, base_addr)

def read_guid(content, pos):
    (ok, val) = read_next_element(content, pos, b"(GUID=", b" ")
    if not ok:
        return (False, None, None)
    pos = val[0]
    guid = val[1].rstrip('\r\n')
    return (True, pos, guid)

def read_image(content, pos):
    (ok, val) = read_next_element(content, pos, b"IMAGE=", b")")
    if not ok:
        return (False, None, None)
    pos = val[0]
    image = val[1].rstrip('\r\n')
    return (True, pos, image)

def parse_map_file(tracker, map_file):
    """Parse the 'map_file' and return a list of [base_address, image]
    for all valid modules. A valid module syntax consists of three
    lines, where the first line contains the base address, the second
    line the GUID, and the third line the image."""
    if not os.access(map_file, os.R_OK):
        raise cli.CliError("Missing read permission for map file '%s'" % (
            map_file))
    map_info = []
    pos = 0
    with open(map_file, "rb") as f:
        try:
            content = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError as e:
            raise cli.CliError("Unable to read %s (%s)" % (map_file, str(e)))
        while True:
            (ok, pos, base_addr) = read_base_addr(content, pos)
            if not ok:
                break

            # Ignore the rest of the line.
            (ok, pos) = next_line(content, pos)
            if not ok:
                break

            # The next line should contain a GUID and should not be empty.
            if is_empty_line(content, pos):
                continue

            # Parse GUID to validate syntax, but ignore the value since the
            # tracker does not handle GUIDs.
            (ok, guid_pos, _) = read_guid(content, pos)
            if not ok:
                continue
            pos = guid_pos

            # Ignore the rest of the line.
            (ok, pos) = next_line(content, pos)
            if not ok:
                break

            # The next line should contain an IMAGE, and not an empty line
            # to avoid that image is taken from the next module.
            if is_empty_line(content, pos):
                simics.SIM_log_info(2, tracker, 0, 'Ignore module at address'
                                    ' 0x%x which lacks image path')
                continue


            (ok, image_pos, image) = read_image(content, pos)
            if not ok:
                simics.SIM_log_info(2, tracker, 0, 'Cannot read image path for'
                                    ' module at address 0x%x')
                continue  # ignore module if no IMAGE
            pos = image_pos

            map_info.append([base_addr, image])
    return map_info

def save_params(tracker_name, params, filename, overwrite):
    try:
        framework.save_parameters_file(filename, tracker_name, params,
                                       overwrite)
    except framework.FrameworkException as e:
        raise cli.CliError(str(e))
    print("Saved parameters to %s" % filename)

def verify_and_set_pre_dxe_range(pre_dxe_enabled, pre_dxe_start,
                                 pre_dxe_size):
    if pre_dxe_enabled:
        if pre_dxe_size is None:
            raise cli.CliError(
                "To enable pre-DXE tracking pre-dxe-size must be provided.")

        if pre_dxe_start is None:
            raise cli.CliError(
                "To enable pre-DXE tracking pre-dxe-start must be provided.")
    else:
        if pre_dxe_start is not None:
            raise cli.CliError(
                "The argument pre-dxe-start has been set even though pre-DXE"
                " tracking has not been enabled with"
                " -enable-pre-dxe-tracking.")
        if pre_dxe_size is not None:
            raise cli.CliError(
                "The argument pre-dxe-size has been set even though pre-DXE"
                " tracking has not been enabled with"
                " -enable-pre-dxe-tracking.")
        pre_dxe_start = 0
        pre_dxe_size = 0
    return (pre_dxe_start, pre_dxe_size)

def default_dxe_start():
    return 0

# Set default DXE range to 4 GB. We assume that PEI is loaded into the low 4 GB
# memory range (which is always true for 32-bit PEI). If this is not the case,
# the user must override this range or we will have to improve the detect,
# perhaps by traversing the memory map.
def default_dxe_size():
    return 0x100000000

def verify_and_set_dxe_range(dxe_enabled, dxe_start, dxe_size):
    if dxe_enabled:
        if dxe_start is None and dxe_size is None:
            dxe_start = default_dxe_start()
            dxe_size = default_dxe_size()
        else:
            if (dxe_start is None) or (dxe_size is None):
                raise cli.CliError(
                    "Either or both of dxe-start and dxe-size must be"
                    " provided.")
            if dxe_size == 0:
                raise cli.CliError(
                    "The argument dxe-size must be greater than zero.")
    else:
        if dxe_start is not None:
            raise cli.CliError(
                "The argument 'dxe-start' has been set to %d even though DXE"
                " tracking has been disabled with -disable-dxe-tracking." % (
                    dxe_start))
        if dxe_size is not None:
            raise cli.CliError(
                "The argument 'dxe-size' has been set to %d even though DXE"
                " tracking has been disabled with -disable-dxe-tracking." % (
                    dxe_size))
        dxe_start = 0
        dxe_size = 0
    return (dxe_start, dxe_size)

def default_exec_scan_size():
    return 0x50000

def verify_and_set_exec_scan_size(arch, exec_enabled, exec_scan_size):
    if not exec_enabled and exec_scan_size is not None:
        raise cli.CliError(
            "The argument 'exec-scan-size' has been set to %d even though"
            " execution tracking has been disabled with"
            " -disable-execution-tracking." % exec_scan_size)

    if exec_scan_size is None:
        exec_scan_size = default_exec_scan_size()
    elif exec_scan_size <= 0:
        raise cli.CliError(
            "The 'exec-scan-size' set to %d is not valid."
            " Please use a strictly positive number.")

    return exec_scan_size

def print_tracking_table(map_file, pre_dxe, dxe, hand_off, smm, exec_tr,
                         notification):
    properties = [
        (simics.Table_Key_Columns, [
            [(simics.Column_Key_Name, 'Tracking Technique')],
            [(simics.Column_Key_Name, 'State')],
            [(simics.Column_Key_Name, 'SEC and PEI (static)'),
             (simics.Column_Key_Alignment, 'center')],
            [(simics.Column_Key_Name, 'PEI (dynamic)'),
             (simics.Column_Key_Alignment, 'center')],
            [(simics.Column_Key_Name, 'DXE'),
             (simics.Column_Key_Alignment, 'center')],
            [(simics.Column_Key_Name, 'SMM'),
             (simics.Column_Key_Alignment, 'center')],
            [(simics.Column_Key_Name, 'FSP'),
             (simics.Column_Key_Alignment, 'center')],
            [(simics.Column_Key_Name, 'Hand-off'),
             (simics.Column_Key_Alignment, 'center')],
        ])]

    configured = {True: 'Configured', False: 'Disabled'}
    is_tracking = {True: 'Yes', False: 'No'}
    data = [
        ['Map File', configured[map_file],
         is_tracking[map_file], '--', '--', '--', '--', '--'],
        ['Pre-DXE', configured[pre_dxe],
         '--', is_tracking[pre_dxe],  '--', '--', '--', '--'],
        ['DXE', configured[dxe],
         '--', '--', is_tracking[dxe], '--', '--', '--'],
        ['SMM', configured[smm],
         '--', '--', '--', is_tracking[smm], '--', '--'],
        ['Execution', configured[exec_tr],
         is_tracking[exec_tr], is_tracking[exec_tr], '--', '--',
         is_tracking[exec_tr], '--'],
        ['Notification', configured[notification],
         is_tracking[notification], is_tracking[notification],
         is_tracking[notification], '--', '--', '--'],
        ['Hand-off', configured[hand_off],
         '--', '--', '--', '--', '--', is_tracking[hand_off]],
    ]

    t = table.Table(properties, data)
    print(t.to_string(force_max_width=79, no_row_column=True))

def cpu_arch(tracker):
    cpus = tracker.parent.iface.osa_machine_query.get_all_processors(tracker)
    if not cpus:
        raise cli.CliError("Unable to locate any processors")
    prev_arch = None
    for cpu in cpus:
        arch = cpu.iface.processor_info_v2.architecture()
        if prev_arch is not None and prev_arch != arch:
            raise cli.CliError("Not all cpus are of same kind")
    return arch

def verify_supported_arch(arch):
    unsupported_msg = f"Unsupported CPU architecture: '{arch}'"
    if arch == "risc-v":
        if not cli.tech_preview_enabled('uefi-fw-tracker-risc-v'):
            suggested_cmd = 'enable-tech-preview uefi-fw-tracker-risc-v'
            raise cli.CliError(
                f"{unsupported_msg}. Please run '{suggested_cmd}' first.")
        return
    if arch == "arm64":
        return
    if arch in ("x86", "x86-64"):
        return
    raise cli.CliError(unsupported_msg)

def parse_args_by_arch(arch, enable_pre_dxe, disable_dxe, disable_hand_off,
                       disable_exec, disable_notification, disable_smm,
                       disable_reset):
    is_arm = arch == "arm64"
    is_riscv = arch == "risc-v"
    return (enable_pre_dxe, not disable_dxe, not disable_hand_off,
            not disable_exec,
            False if (is_arm or is_riscv) else not disable_notification,
            False if (is_arm or is_riscv) else not disable_smm,
            False if (is_arm or is_riscv) else not disable_reset)

def uefi_detect(tracker, output, overwrite, verbose, load, map_file,
                enable_pre_dxe, pre_dxe_start, pre_dxe_size,
                disable_dxe, disable_hand_off, dxe_start, dxe_size,
                disable_exec, exec_scan_size, disable_notification, disable_smm,
                disable_reset):
    if overwrite and load and not output:
        raise cli.CliError(
            'Cannot use -overwrite together with -load without param-file set')

    tracker_comp = simics.SIM_object_parent(tracker)
    arch = cpu_arch(tracker)
    verify_supported_arch(arch)

    (pre_dxe, dxe, hand_off, exec_tr, notification, smm,
     reset) = parse_args_by_arch(
         arch, enable_pre_dxe, disable_dxe, disable_hand_off, disable_exec,
         disable_notification, disable_smm, disable_reset)

    if pre_dxe and arch == 'arm64':
        raise cli.CliError('Pre-DXE tracking is not supported on ARM platforms')

    if pre_dxe and arch == 'risc-v':
        raise cli.CliError('Pre-DXE tracking is not supported on RISC-V platforms')

    if (not map_file and not pre_dxe and not exec_tr and not dxe
        and not notification and not smm):
        raise cli.CliError('All tracking options cannot be disabled')

    if not dxe and hand_off:
        raise cli.CliError('OS hand-off requires DXE tracking')

    if map_file is not None:
        map_info = parse_map_file(tracker, map_file)
    else:
        map_info = []

    (pre_dxe_start, pre_dxe_size) = verify_and_set_pre_dxe_range(
        pre_dxe, pre_dxe_start, pre_dxe_size)

    (dxe_start, dxe_size) = verify_and_set_dxe_range(
        dxe, dxe_start, dxe_size)

    exec_scan_size = verify_and_set_exec_scan_size(
        arch, exec_tr, exec_scan_size)

    # The keys in this dictionary are defined in uefi-fw-tracker-params.h
    # with the prefix PARAM_.
    params = {"map_info": map_info,
              "map_file": map_file,
              "pre_dxe_tracking": pre_dxe,
              "pre_dxe_start": pre_dxe_start,
              "pre_dxe_size": pre_dxe_size,
              "dxe_tracking": dxe,
              "hand_off_tracking": hand_off,
              "dxe_start": dxe_start,
              "dxe_size": dxe_size,
              "exec_scan_size": exec_scan_size,
              "exec_tracking": exec_tr,
              "notification_tracking": notification,
              "smm_tracking": smm,
              "reset_tracking": reset,
              "tracker_version": conf.sim.version}
    tracker_type = "uefi_fw_tracker"
    if load:
        try:
            framework.set_parameters(tracker_comp, [tracker_type, params])
        except framework.FrameworkException as e:
            raise cli.CliError(e)
    elif output is None:
        output = default_params_file()

    if output:
        save_params(tracker_type, params, output, overwrite)

    # Only show table if save_params succeeded.
    if verbose:
        print_tracking_table(
            bool(map_file), pre_dxe, dxe, hand_off, smm, exec_tr, notification)

def uefi_detect_comp(tracker_comp, *args):
    tracker_obj = tracker_comp.iface.osa_tracker_component.get_tracker()
    uefi_detect(tracker_obj, *args)

def default_params_file():
    return 'uefi.params'

def add_uefi_detect_command(cls, fun):
    cli.new_command(
        'detect-parameters', fun,
        args = [cli.arg(cli.filename_t(), 'param-file', '?', None),
                cli.arg(cli.flag_t, '-overwrite'),
                cli.arg(cli.flag_t, '-verbose'),
                cli.arg(cli.flag_t, '-load'),
                cli.arg(cli.filename_t(exist=True), 'map-file', '?'),
                cli.arg(cli.flag_t, '-enable-pre-dxe-tracking'),
                cli.arg(cli.int_t, "pre-dxe-start", "?"),
                cli.arg(cli.int_t, "pre-dxe-size", "?"),
                cli.arg(cli.flag_t, '-disable-dxe-tracking'),
                cli.arg(cli.flag_t, '-disable-hand-off-tracking'),
                cli.arg(cli.int_t, "dxe-start", "?"),
                cli.arg(cli.int_t, "dxe-size", "?"),
                cli.arg(cli.flag_t, '-disable-execution-tracking'),
                cli.arg(cli.int_t, "exec-scan-size", "?"),
                cli.arg(cli.flag_t, '-disable-notification-tracking'),
                cli.arg(cli.flag_t, '-disable-smm-tracking'),
                cli.arg(cli.flag_t, '-disable-reset-support')],
        cls = cls,
        short = "try to detect settings for the UEFI tracker",
        see_also = ['<osa_parameters>.load-parameters'],
        doc = """
Detect the parameters to use with the UEFI Firmware tracker and write
to a parameter file. For information about tracking techniques, see
<cite>Analyzer User's Guide</cite>.

The optional <arg>param-file</arg> argument is used to specify where to save
the parameters, the default is <file>%s</file>. If this argument is left out
and the <tt>-load</tt> flag is used then no parameters will be saved.

The <tt>-load</tt> flag can be used to load the newly detected parameters
directly after detection.

The optional <tt>-overwrite</tt> flag tells the detect command to
overwrite the file specified by the <arg>param-file</arg> argument, if it
exists.

Use <tt>-verbose</tt> to show a configuration overview of the
tracker configuration.

Configure map file tracking by setting the <arg>map-file</arg>
argument to the <em>UEFI build's map-file</em>.

Pre-DXE tracking is only supported for X86 platform and is enabled
by setting <tt>-enable-pre-dxe-tracking</tt>.
This requires that the scanning range which will be scanned for
dynamic PEI modules by the tracker is set with
<arg>pre-dxe-start</arg> and <arg>pre-dxe-size</arg>.

DXE tracking is enabled by default and can be disabled with
<tt>-disable-dxe-tracking</tt>. The default scanning range
to locate EFI_SYSTEM_TABLE_POINTER is from 0 to 4 GB, but
this range can be modified by specifying <arg>dxe-start</arg>
and <arg>dxe-size</arg>.

OS hand-off tracking tracks hand-off to the OS from UEFI, and
when this happens, only SMM and reset-tracking are preserved. OS hand-off
tracking requires DXE tracking, which means that if DXE tracking is disabled,
OS hand-off tracking must be disabled as well. To disable OS hand-off tracking,
use <tt>-disable-hand-off-tracking</tt>.

Execution tracking is enabled by default and can be disabled with
<tt>-disable-execution-tracking</tt>. This tracking requires that the
scanning size is as large as the largest module in the system and
defaults to %d bytes. To modify the scanning size, set
<arg>exec-scan-size</arg>.

Notification tracking is only available on an X86 platform, and is enabled by
default on X86. To disable notification tracking, use
<tt>-disable-notification-tracking</tt>. This tracking requires that
notification support has been added to the UEFI system.

SMM tracking is only available on an X86 platform, and is enabled by default on
X86, but can be disabled with <tt>-disable-smm-tracking</tt>.

Processor reset monitoring is only available on an X86 platform, and is enabled
by default on X86, but can be disabled with <tt>-disable-reset-support</tt>.

For further details, see the <cite>Analyzer User's Guide</cite>.
""" % (default_params_file(), default_exec_scan_size()))

def basename(image_name):
    """Returns the basename for the path in 'image_name'. Since we don't know
    which slashes are used, we use the most common slashes
    from 'image_name' as separators."""
    if image_name is None:
        return "<unknown>"

    if image_name.count('\\') > image_name.count('/'):
        sep = '\\'
    else:
        sep = '/'
    return image_name.split(sep)[-1]

def mappings_table_properties():
    return [
        (table.Table_Key_Name, "Loaded modules"),
        (table.Table_Key_Description,
         "Loaded UEFI modules known to the tracker"),
        (table.Table_Key_Default_Sort_Column, "Module"),
        (table.Table_Key_Columns, [
            [(table.Column_Key_Name, "Module"),
             (table.Column_Key_Description,
              "The EFI module base file name.")],
            [(table.Column_Key_Name, "Loaded Address"),
             (table.Column_Key_Description,
              "Address where the module is loaded."),
             (table.Column_Key_Int_Radix, 16)],
            [(table.Column_Key_Name, "Size"),
             (table.Column_Key_Description,
              "Size of module in memory."),
             (table.Column_Key_Footer_Sum, True),
             (table.Column_Key_Footer_Mean, True),
             (table.Column_Key_Int_Radix, 16)],
            [(table.Column_Key_Name, "Adjusted Address"),
             (table.Column_Key_Description,
              "Address where symbol information is loaded."),
             (table.Column_Key_Hide_Homogeneous, ""),
             (table.Column_Key_Int_Radix, 16)],
            [(table.Column_Key_Name, "Adjusted Size"),
             (table.Column_Key_Description,
              "Size of the symbol information file."),
             (table.Column_Key_Hide_Homogeneous, ""),
             (table.Column_Key_Int_Radix, 16)],
        ])]

def get_mappings(mapper, no_unknown_maps):
    if mapper.root_node is None:
        return []

    (error, mappings) =  mapper.iface.osa_target_info.memory_map(
        mapper.uefi_node)

    if error:
        return []

    maps = []
    for m in mappings:
        if m['image'] is None and no_unknown_maps:
            continue
        mapping = [basename(m['image']), m['loaded_address'], m['loaded_size']]

        if (m.get('adjusted_address') is not None
            and m['loaded_address'] != m['adjusted_address']):
            mapping += [m['adjusted_address'], m['adjusted_size']]
        else:
            mapping += ["", ""]
        maps.append(mapping)
    return maps

def list_modules(mapper, no_unknown_maps, reg_exp, *table_args):
    tracker_obj = mapper.tracker
    if not tracker_obj.enabled:
        raise cli.CliError('Tracker not enabled')
    data = get_mappings(mapper, no_unknown_maps)
    out_data = data
    msg = ""
    if reg_exp:
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error as e:
            raise cli.CliError("The regular expression '%s' is not valid: %s"
                               % (reg_exp, e))

        out_data = [r for r in data if ins_re.match(str(r[0]))]
        org_num_rows = len(data)
        new_num_rows = len(out_data)
        msg = "Table reduced from %d to %d rows\n" % (
            org_num_rows, new_num_rows)

    msg += table.get(mappings_table_properties(), out_data, *table_args)

    return cli.command_return(value=out_data, message=msg)

def list_modules_tracker_comp(tracker_comp, no_unknown_maps, reg_exp,
                              *table_args):
    return list_modules(tracker_comp.mapper_obj, no_unknown_maps, reg_exp,
                        *table_args)

def add_list_modules_command(cls, fun):
    table.new_table_command(
        'list-modules', fun,
        args = [cli.arg(cli.flag_t, "-no-unknown-modules"),
                cli.arg(cli.str_t, "module-regexp", "?", None)],
        cls = cls,
        short = "list loaded modules",
        doc = """List all loaded modules known by the tracker.
        To search for a specific module name, specify a module
        name filter with <arg>module-regexp</arg>.

        To filter out the modules for which no module name has
        been found, specify <tt>-no-unknown-modules</tt>.""",
        sortable_columns = ["Module", "Loaded Address", "Size"])

def active_module_table_properties():
    return [
        (table.Table_Key_Name, "Active modules"),
        (table.Table_Key_Description,
         "Active UEFI modules where CPUs are executing"),
        (table.Table_Key_Default_Sort_Column, "Module"),
        (table.Table_Key_Columns, [
            [(table.Column_Key_Name, "Module"),
             (table.Column_Key_Description,
              "The EFI module base file name.")],
            [(table.Column_Key_Name, "CPU"),
             (table.Column_Key_Description,
              "The CPU executing in this module.")],
            [(table.Column_Key_Name, "Loaded Address"),
             (table.Column_Key_Description,
              "Address where the module is loaded."),
             (table.Column_Key_Int_Radix, 16)],
            [(table.Column_Key_Name, "Size"),
             (table.Column_Key_Description,
              "Size of module in memory."),
             (table.Column_Key_Int_Radix, 16)]
        ])]

def cpus_in_module(tracker_obj, mapping):
    cpus_inside = []
    for cpu in tracker_obj.parent.iface.osa_machine_query.get_all_processors(
            tracker_obj):
        try:
            processor_info = simics.SIM_get_interface(cpu, 'processor_info')
            pc = processor_info.get_program_counter()
            if mapping[1] <= pc < mapping[1] + mapping[2]:
                cpus_inside.append(cpu)
        except simics.SimExc_Lookup:
            continue
    return cpus_inside

def active_module(mapper, arg, *table_args):
    tracker_obj = mapper.tracker
    machine_iface = tracker_obj.parent.iface.osa_machine_query
    all_cpus = machine_iface.get_all_processors(tracker_obj)
    cpu_specified = False
    if arg is None:
        cpus = [cli.current_cpu_obj()]
        cpu_specified = True
    else:
        (t, v, name) = arg
        if name == "-all":
            cpus = all_cpus
        else:
            cpus = [v]
            cpu_specified = True

    if cpu_specified and cpus[0] not in all_cpus:
        raise cli.CliError(
            "The cpu %s is not tracked by the UEFI tracker." % (
                cpus[0].name))

    out_data = []
    for mapping in get_mappings(mapper, False):
        for cpu in cpus_in_module(tracker_obj, mapping):
            if cpu in cpus:
                out_data.append([mapping[0], cpu, mapping[1], mapping[2]])
    if out_data:
        msg = table.get(active_module_table_properties(), out_data, *table_args)
    else:
        msg = "No CPU is currently executing in an UEFI module."
    return cli.command_return(value=out_data, message=msg)

def active_module_tracker_comp(tracker_comp, flag_id, arg, *table_args):
    return active_module(tracker_comp.mapper_obj, flag_id, arg, *table_args)

def add_active_module_command(cls, fun):
    table.new_tech_preview_table_command(
        'active-module', 'uefi-fw-tracker-active-modules', fun,
        args = [cli.arg((cli.obj_t('processor', 'processor_info'), cli.flag_t),
                        ("cpu-name", "-all"), "?")],
        cls = cls,
        doc = """List modules where CPUs are executing. The current processor is
        automatically selected unless a processor is given by the
        <arg>cpu-name</arg> argument, or the <tt>-all</tt> argument is used to
        list the active modules for all processors that the os awareness system
        is aware of.""",
        sortable_columns = ["Module", "Loaded Address", "Size", "CPU"])

tracker_cls = 'uefi_fw_tracker'
tracker_comp_cls = 'uefi_fw_tracker_comp'
mapper_cls = 'uefi_fw_mapper'
def add_uefi_fw_tracker_commands():
    cli.new_info_command(tracker_cls, get_uefi_fw_tracker_info)
    cli.new_status_command(tracker_cls, get_uefi_fw_tracker_status)
    cli.new_info_command(mapper_cls, get_uefi_fw_mapper_info)
    cli.new_status_command(mapper_cls, get_uefi_fw_mapper_status)
    add_uefi_detect_command(tracker_cls, uefi_detect)
    add_uefi_detect_command(tracker_comp_cls, uefi_detect_comp)
    add_list_modules_command(mapper_cls, list_modules)
    add_list_modules_command(tracker_comp_cls, list_modules_tracker_comp)
    add_active_module_command(mapper_cls, active_module)
    add_active_module_command(tracker_comp_cls, active_module_tracker_comp)

add_uefi_fw_tracker_commands()
