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


from contextlib import contextmanager
import os
import simics
import cli
from simmod.os_awareness import framework
from . import tracker_util as tu

def save_params(tracker_name, params, filename, overwrite):
    try:
        framework.save_parameters_file(filename, tracker_name, params,
                                       overwrite)
    except framework.FrameworkException as e:
        raise cli.CliError(str(e))

@contextmanager
def parse_symbols(symbol_file, is_elf):
    if is_elf:
        parser = tu.ElfParser(simics.SIM_get_debugger().iface.tcf_elf,
                              symbol_file)
    else:
        parser = tu.PlainParser(symbol_file)
    try:
        yield parser
    finally:
        parser.close()

def get_linux_detect_hints(symbol_file, is_elf, base_address, ram_base,
                           randomize_base, kernel_modules):
    hints = {}
    if base_address is not None:
        hints['base_address'] = base_address
    if ram_base is not None:
        hints['ram_base'] = ram_base
    if randomize_base is not None:
        hints['randomize_base'] = randomize_base
    if kernel_modules is not None:
        hints['kernel_modules'] = kernel_modules

    if symbol_file:
        try:
            with parse_symbols(symbol_file, is_elf) as symbols:
                for (key, symbol) in (
                        ('current_task', '_current_task'),  # Used in ARCv2
                        ('current_task', 'current_task'),
                        # As of kernel v6.2 current task is first placed first
                        # in pcpu_hot struct. The current_task symbol is then no
                        # longer exposed.
                        ('current_task', 'pcpu_hot'),
                        ('current_task', 'per_cpu__current_task'),
                        ('pcpu_base_addr', 'pcpu_base_addr'),
                        ('pcpu_unit_size', 'pcpu_unit_size'),
                        ('per_cpu_start', '__per_cpu_start'),
                        ('per_cpu_end', '__per_cpu_end'),
                        ('gdt_page', 'gdt_page'),  # X86 only
                        # The lapic_* functions are used on X86 to figure out
                        # randomization.
                        ('lapic_events', 'lapic_events'),
                        ('lapic_timer_shutdown', 'lapic_timer_shutdown'),
                        ('lapic_timer_set_periodic',
                         'lapic_timer_set_periodic'),
                        ('lapic_timer_set_oneshot', 'lapic_timer_set_oneshot'),
                        ('lapic_timer_shutdown', 'lapic_timer_shutdown'),
                        # Following module* symbols are needed for kernel module
                        # handling.
                        ('modules', 'modules'),
                        ('module_loaded_func', '.do_one_initcall'), # PPC 64
                        ('module_loaded_func', 'do_one_initcall'), # Old kernel
                        # If several functions for module loaded are present,
                        # then we prefer do_init_module, so that is put last in
                        # this tuple.
                        ('module_loaded_func', 'do_init_module'),
                        ('entry_task', '__entry_task'),  # Used in ARM64
                        ('kasan_init', 'kasan_init'),  # Used in ARM64
                        ('kimage_voffset', 'kimage_voffset'), # Used in ARM64
                        ('physvirt_offset', 'physvirt_offset'), # Used in ARM64
                        ('vabits_actual', 'vabits_actual'), # Used in ARM64
                        ('memstart_addr', 'memstart_addr'), # Used in ARM64
                        ('finish_task_switch', 'finish_task_switch')):
                    (ok, ret) = symbols.get_symbol_info(symbol)
                    if ok:
                        (addr, size) = ret
                        hints[key] = addr
        except tu.DetectException as e:
            raise cli.CliError("%s" % e)

        if None in list(hints.values()):
            raise cli.CliError("The symbol file %s was not helpful to the"
                               " autodetector. Possible reasons include a"
                               " kernel version prior to 2.6.32 (in which case"
                               " a symbol file is not needed), and a version"
                               " mismatch between the symbol file and the"
                               " running kernel." % symbol_file)
    return hints

def save_and_load_detected_parameters(tracker, output, params, load, overwrite):
    tracker_type = 'linux_tracker'

    if output is not None:
        filenames = [output]
        # Params will contain a list of found parameters. If more than one
        # parameter in the list then the detector could not determine which one
        # was correct.
        if len(params) > 1:
            if not load:
                print(f'There were {len(params)} possible parameter settings'
                      ' possible')
            for i in range(1, len(params)):
                filenames.append(output + '.' + str(i))

        for (f, p) in zip(filenames, params):
            save_params(tracker_type, p, f, overwrite)
            print(f'Saved autodetected parameters to {f}')

    if load:
        if len(params) > 1:
            raise cli.CliError('Unable to load parameters as there were'
                               f' {len(params)} possible parameters')

        tracker_comp = simics.SIM_object_parent(tracker)
        try:
            framework.set_parameters(tracker_comp, [tracker_type, params[0]])
        except framework.FrameworkException as e:
            raise cli.CliError(e)

def default_output_file():
    return 'detect.params'

def linux_detect(tracker, output, name, base_address, symbol_file, load,
                 overwrite, rt_kernel, ram_base, randomize_base,
                 kernel_modules):
    if not overwrite and output and os.path.exists(output):
        raise cli.CliError(
            "Unable to detect Linux parameters, '%s' already exists" % output)

    if overwrite and load and not output:
        raise cli.CliError(
            'Cannot use -overwrite together with -load without param-file set')
    is_elf = None
    if symbol_file:
        try:
            with open(symbol_file, "rb") as f:
                is_elf = f.read(4) == b"\x7fELF"
        except IOError as e:
            raise cli.CliError("Failed to open symbol file: %s" % e)

    hints = get_linux_detect_hints(symbol_file, is_elf, base_address, ram_base,
                                   randomize_base, kernel_modules)
    if name:
        hints['name'] = name
    if rt_kernel:
        hints['rt_kernel'] = 1
    (success, params_or_msg) = tracker.iface.osa_tracker_parameters.detect(
        [symbol_file, hints])

    if not success:
        raise cli.CliError(params_or_msg)

    if not load and output is None:
        output = default_output_file()

    save_and_load_detected_parameters(tracker, output, params_or_msg, load,
                                      overwrite)

def linux_comp_detect(tracker_comp, *args):
    linux_detect(tracker_comp.tracker_obj, *args)

# TODO: We need to figure out how to save parameters in the new framework. For
# now, generate a parameters file on the same format as the previous. The
# command documentation needs to be updated.
def add_lx_detect_command(cls, detector):
    cli.new_command(
        'detect-parameters', detector,
        args = [cli.arg(cli.filename_t(), 'param-file', '?', None),
                cli.arg(cli.str_t, 'version-string', '?', None),
                cli.arg(cli.integer_t, 'base-address', '?', None),
                cli.arg(cli.filename_t(exist=True), 'symbol-file', '?', None),
                cli.arg(cli.flag_t, '-load'),
                cli.arg(cli.flag_t, '-overwrite'),
                cli.arg(cli.flag_t, '-real-time'),
                cli.arg(cli.integer_t, 'ram-base', '?', None),
                cli.arg(cli.bool_t(), 'randomize-base', '?', None),
                cli.arg(cli.bool_t(), 'kernel-modules', '?', None)],
        cls = cls,
        short = "try to detect settings for the Linux tracker",
        see_also = ['<osa_parameters>.load-parameters'],
        doc = """

Detect the parameters to use with the Linux tracker. For this to work, Linux
must be up and running on the simulated machine. If more than one possible
solution is found (the tracker could not identify which is correct), each
possible solution will be saved, by adding a suffix to the given parameter file
name.

The optional <arg>param-file</arg> argument is used to specify where to save
the parameters, the default is 'detect.params'. If this argument is left out
and the <tt>-load</tt> flag is used then no parameters will be saved.

The <tt>-load</tt> flag can be used to load the newly detected parameters
directly after detection.

The optional <arg>version-string</arg> argument can be used to specify
information about the Linux version running on the system. This will be the
name of the root node in the node tree.

The optional <arg>base-address</arg> argument can be used to specify the kernel
base address. Unless this option is given, the tracker will use a set of
predefined values, which are platform dependent. For 32-bit x86 kernels, the
tracker will use the symbols, if provided, to determine the kernel base
address. If the target is running a kernel with a kernel base that is not part
of the default values (usually 0xc0000000) the user may specify this option in
order to get a successful parameter detection. It can also be provided in
order to speed up the detection on some platforms.

The optional <arg>ram-base</arg> argument can be used to specify the
physical address for the base of the ram in which the kernel is
loaded. This is currently only used when tracking Linux on ARM systems.

For many targets it is possible to detect parameters without providing any
symbols. For other targets, the tracker will require the user to provide debug
information by using the <arg>symbol-file</arg> argument. Debug information can
normally be found in the <file>vmlinux</file> file when the kernel is compiled
with debug information.

For some targets it may be enough to provide plain symbols, such as
<file>/proc/kallsyms</file> on the target or the <file>System.map</file> file
associated with the kernel. The exact needs depends on platform and kernel
version.

The optional <tt>-real-time</tt> argument should be used when
detecting parameters for a real-time kernels if only plain symbols are
given. If this is not used for that case then the detection can fail to
understand that this is a real-time kernel and the detected parameters
may be incorrect for that kernel. If <file>vmlinux</file> symbols are
given this argument should not be needed.

The optional <arg>randomize-base</arg> forces the detection to either treat
the kernel as having randomised base (the <tt>RANDOMIZE_BASE</tt>
configuration option for the kernel) or to not have, depending on if this
argument is set to TRUE or FALSE. If this argument is not set then the
detector will try to determine whether or not the kernel has randomized base.

The optional <arg>kernel-modules</arg> argument is used to either leave out
detection of kernel modules, when FALSE, or to force kernel modules to be
detected, when TRUE. If TRUE and kernel module parameters cannot be found then
detect will fail. If this is not set then kernel module parameters will be
included if found, but detection will not fail if such parameters are not found.

The optional <tt>-overwrite</tt> flag specifies that the parameters
file should be overwritten if it exists.
""")

def get_lx_tracker_info(lx_tracker):
    return [(None, [("OSA Admin", lx_tracker.osa_admin)])]

def get_tracked_cpus(processors_attr):
    tracked_cpus = []
    for (cpu, tracked, _) in processors_attr:
        if tracked:
            tracked_cpus.append(cpu)
    return tracked_cpus

def get_lx_tracker_status(lx_tracker):
    return [(None, [("Enabled", lx_tracker.enabled),
                    ("Booted", lx_tracker.booted),
                    ("Number of tasks", len(lx_tracker.task_cache)),
                    ("Tracked cpus", get_tracked_cpus(lx_tracker.processors))])]

def get_lx_mapper_info(lx_mapper):
    return [(None, [("OSA node tree admin", lx_mapper.node_tree_admin),
                    ("Tracker state notification object",
                     lx_mapper.tracker_state_notification),
                    ("Tracker state query object",
                     lx_mapper.tracker_state_query),
                    ("Ignore empty task names", lx_mapper.ignore_empty_name)])]

def get_lx_mapper_status(lx_mapper):
    return [(None, [("Enabled", lx_mapper.enabled),
                    ("Booted", lx_mapper.booted),
                    ("Number of entities", len(lx_mapper.entities)),
                    ("Known cpus",
                     [cpu_data[0] for cpu_data in lx_mapper.known_cpus])])]

log_syscalls_cids = {}

def get_linux_mapper_root_node(mapper, osa_admin):
    root_id = mapper.base_node_ids[0]

    nt_query = osa_admin.iface.osa_node_tree_query
    if (not mapper.enabled) or nt_query.get_mapper(root_id) != mapper:
        return None

    return root_id

def log_syscalls_cb(mapper, osa_admin, cpu, node_id, event_name, event_data):
    syscall_name = event_data["name"]
    syscall_number = event_data["number"]
    simics.SIM_log_info(1, mapper, 0, "Syscall: '%s' (%d) on node %d (%s)"
                        % (syscall_name, syscall_number, node_id, cpu.name))

def log_syscalls_mapper(mapper, disable):
    osa_admin = mapper.tracker.osa_admin
    nt_notify = osa_admin.iface.osa_node_tree_notification
    global log_syscalls_cids
    log_syscalls_cid = log_syscalls_cids.get(mapper)

    if disable:
        if log_syscalls_cid != None:
            nt_notify.cancel_notify(log_syscalls_cid)
            log_syscalls_cids[mapper] = None
        return

    if not mapper.enabled:
        raise cli.CliError(
            "Can not enable logging of syscalls when mapper is disabled")

    if log_syscalls_cid != None:
        raise cli.CliError("Syscalls logging already enabled")

    root_id = get_linux_mapper_root_node(mapper, osa_admin)
    if root_id == None:
        raise cli.CliError("No root ID found for '%s'" % (mapper.name,))

    log_syscalls_cid = nt_notify.notify_event(
        root_id, "syscall", True, log_syscalls_cb, mapper)
    log_syscalls_cids[mapper] = log_syscalls_cid

def log_syscalls_comp(tracker_comp, *args):
    mapper_obj = tracker_comp.iface.osa_tracker_component.get_mapper()
    log_syscalls_mapper(mapper_obj, *args)

def add_log_syscalls_command(cls, fn):
    cli.new_command(
        'log-syscalls', fn, [cli.arg(cli.flag_t, '-disable')],
        cls = cls, type = ['Debugging'],
        short = 'start logging system calls',
        doc = """
Starts logging all system calls. For each system call, a line will be
written to the Simics log. With the <tt>-disable</tt> flag, logging is
disabled.""")

def any_address_over_32bit(modules):
    for module_data in modules:
        (module_addr, _, sections) = module_data[:3]
        if module_addr >= (1 << 32):
            return True
        for (addr, _) in sections:
            if addr >= (1 << 32):
                return True
    return False

def is_executable_section(section_addr, text_ranges):
    for (start, end) in text_ranges:
        if start <= section_addr < end:
            return True
    return False

def list_kernel_modules(tracker_obj, module, sections_option):
    if not tracker_obj.enabled:
        raise cli.CliError("Tracker not enabled")
    only_executable = False
    exclude_sections = False
    if sections_option:
        (_, _, flag_name) = sections_option
        if flag_name == "-exclude-sections":
            exclude_sections = True
        else:
            only_executable = True

    modules = tracker_obj.kernel_modules.copy()
    if modules is False:
        return cli.command_return(message = "Kernel modules are not handled")
    if modules is True:
        return cli.command_return(
            message = "Stable kernel modules not yet found, likely need to"
            " advance simulation a bit into kernel to find modules.")
    msgs = []
    addrs_over_32 = any_address_over_32bit(modules)
    resulting_modules = []
    for module_data in sorted(modules):
        (module_addr, name, mem_types, org_sections) = module_data
        if module and module != name:
            continue

        # Address ranges for text sections (base, end), end address is
        # exclusive.
        text_ranges = [(base, base + size)
                       for (base, size, exe, _) in mem_types if exe]

        if exclude_sections:
            sections = []
        elif only_executable:
            sections = [s for s in org_sections
                        if is_executable_section(s[0], text_ranges)]
        else:
            sections = org_sections
        resulting_modules.append([module_addr, name, sections])
        msgs.append("%s (0x%*x)%s" % (name, 16 if addrs_over_32 else 8,
                                      module_addr,
                                      "" if exclude_sections else ":"))
        for (sect_addr, sect_name) in sorted(sections):
            msgs.append("  0x%0*x: %s" % (16 if addrs_over_32 else 8,
                                          sect_addr, sect_name))
    msg = "\n".join(msgs) if msgs else "No modules found"
    return cli.command_return(value = resulting_modules, message = msg)

def list_kernel_modules_comp(tracker_comp, *args):
    tracker_obj = tracker_comp.iface.osa_tracker_component.get_tracker()
    return list_kernel_modules(tracker_obj, *args)

def module_expander(part, obj):
    # Make this work for both composition and object
    try:
        obj = obj.iface.osa_tracker_component.get_tracker()
    except AttributeError:
        pass
    known_modules = [m[1] for m in obj.kernel_modules.copy()]
    return cli.get_completions(part, known_modules)

def add_list_kernel_modules_command(cls, fn):
    cli.new_command(
        'list-kernel-modules', fn,
        [cli.arg(cli.str_t, "module", "?", None, expander=module_expander),
         cli.arg((cli.flag_t, cli.flag_t),
                 ('-exclude-sections', '-only-executable-sections'), "?",
                 None)],
        cls = cls,
        short = 'list kernel modules',
        doc = """
Lists kernel modules found by the tracker.

By default the sections of the modules will also be outputted, use the
<tt>-exclude-sections</tt> flag to not include sections in the output.

The <tt>-only-executable-sections</tt> flag can be used to only display sections
that are currently found to be executable.
Note that the init sections will only be executable for a short time when init
code is run. After that init sections will no longer be present in memory and
will be excluded from output when using this flag.

The <arg>module</arg> argument can be used to just lite one module, to see
it's address and/or sections.

Returned value is a list of sections on the format:
<pre>[[module address, module name, [section address, section name]*]*]</pre>

If kernel modules are not handled, likely due to kernel modules parameters not
being found when detecting parameters, this function will return NIL and print
a message.""")

def km_path_expander(s):
    # Default combining of nil_t and filename_t expanders does not work. This
    # expander will prefer file name over nil, but will use the nil_t expander
    # if user start to type N, NI or NIL and there is no matching file for
    # that. Otherwise the filename_t expander will be used. This should be good
    # enough.
    nil_exp = cli.nil_t.expand(s)
    file_exp = cli.filename_t(dirs=True).expand(s)
    if nil_exp and not file_exp:
        return nil_exp
    return file_exp

def set_kernel_modules_path(tracker_obj, path):
    tracker_obj.kernel_modules_path = path

def set_kernel_modules_path_comp(tracker_comp, *args):
    tracker_obj = tracker_comp.iface.osa_tracker_component.get_tracker()
    set_kernel_modules_path(tracker_obj, *args)

def add_set_kernel_modules_path_command(cls, fn):
    cli.new_command(
        'set-kernel-modules-path', fn,
        [cli.arg(cli.poly_t("path_or_nil", cli.filename_t(dirs=True),
                            cli.nil_t),
                 "path", expander=km_path_expander)],
        cls = cls,
        short = 'set base path for kernel modules',
        doc = """
Sets a <arg>path</arg> for where the debugger should scan for kernel modules on
host.

When this is set the debugger will try to find kernel modules files that match
the ones found by the Linux tracker under this path (including sub-directories).

The <arg>path</arg> does not have to be an existing host path, it can be any
path or pattern for which a path map can then be applied on in the debugger, in
order to map this to the actual host directory.

If this is set to an empty string then kernel modules will not be scanned for
and the debugger will then only be able to debug kernel modules for which
individual path maps have been added.""")

def add_linux_commands():
    add_lx_detect_command("linux_tracker", linux_detect)
    add_lx_detect_command("linux_tracker_comp", linux_comp_detect)
    cli.new_info_command('linux_tracker', get_lx_tracker_info)
    cli.new_status_command('linux_tracker', get_lx_tracker_status)
    cli.new_info_command('linux_mapper', get_lx_mapper_info)
    cli.new_status_command('linux_mapper', get_lx_mapper_status)
    add_log_syscalls_command("linux_mapper", log_syscalls_mapper)
    add_log_syscalls_command("linux_tracker_comp", log_syscalls_comp)
    add_list_kernel_modules_command("linux_tracker", list_kernel_modules)
    add_list_kernel_modules_command("linux_tracker_comp",
                                    list_kernel_modules_comp)
    add_set_kernel_modules_path_command("linux_tracker",
                                        set_kernel_modules_path)
    add_set_kernel_modules_path_command("linux_tracker_comp",
                                        set_kernel_modules_path_comp)
