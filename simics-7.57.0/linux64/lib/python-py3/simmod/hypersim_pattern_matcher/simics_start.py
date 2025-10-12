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
    arg,
    command_verbose_return,
    flag_t,
    new_command,
    run_command,
)
from simics import *
from hypersim_patterns import hypersim_patterns
import cmputil
import table
import conf

# Keeps track if a new CPU has been created since last hpm-population
new_cpus_created = False

hypersim_enabled = False    # Feature activated at all
ah_enabled = False          # Sub-feature: autohyper
hpm_enabled = False         # Sub-feature: pattern-matcher

# Called when a new object has been created. Check if it's a processor.
def object_created(data, obj):
    if hasattr(obj.iface, "processor_info"):
        global new_cpus_created
        new_cpus_created = True

# Called when all the objects have been created. If we have seen
# processors part of the new config, populate the pattern-matcher.
def objects_created(data, obj):
    global new_cpus_created
    if new_cpus_created:
        if hpm_enabled:
            populate_pattern_matchers(verbose = False)
        if ah_enabled:
            auto_hyper(enable = True, verbose = False)
        new_cpus_created = False

def enable_hypersim():
    global hypersim_enabled
    if not hypersim_enabled:
        hypersim_enabled = True
        SIM_hap_add_callback("Core_Conf_Object_Created",
                             object_created, None)
        SIM_hap_add_callback("Core_Conf_Objects_Created",
                             objects_created, None)

def disable_hypersim():
    global hypersim_enabled
    if hypersim_enabled:
        hypersim_enabled = False
        SIM_hap_delete_callback("Core_Conf_Object_Created",
                                object_created, None)
        SIM_hap_delete_callback("Core_Conf_Objects_Created",
                                objects_created, None)

def enable_hpm(verbose):
    global hpm_enabled
    hpms = []
    if not hpm_enabled:
        hpm_enabled = True
        hpms = populate_pattern_matchers(verbose)
    return hpms

def disable_hpm(verbose):
    global hpm_enabled
    all_hpms = []
    if hpm_enabled:
        hpm_enabled = False
        for o in all_hypersim_pattern_matchers():
            all_hpms.append(o)
        for o in all_hpms:
            # If an object contains several patterns only delete it once
            for p in list(set(o.patterns)):
                if (verbose):
                    print("Removing %s" % (p.name))
                SIM_delete_object(p)

def enable_hypersim_cmd(verbose, no_auto, no_pm):

    # If all sub-features are disabled, we have disabled the feature too.
    if no_auto and no_pm:
        disable_hypersim()
    else:
        enable_hypersim()

    if no_pm:
        disable_hpm(verbose)
    else:
        enable_hpm(verbose)

    enable_autohyper = not no_auto
    auto_hyper(enable = enable_autohyper, verbose = verbose)

    return all_hypersim_pattern_matchers()

# Enable or disable autohyper
def auto_hyper(enable, verbose):
    global ah_enabled
    ah_enabled = enable
    for c in SIM_get_all_processors():
        if not hasattr(c, "auto_hyper_enabled"):
            continue

        c.auto_hyper_enabled = enable
        if verbose:
            if enable:
                print("activating automatic hypersimulation on %s" % (
                    c.name,))
            else:
                print("deactivating automatic hypersimulation on %s" % (
                    c.name,))

# Only get the processors that implement processor_info, step and cycle
def get_processors():
    return list(SIM_object_iterator_for_interface(['processor_info',
                                                   'cycle', 'step']))

def populate_pattern_matchers(verbose):

    # Creates a _hpm%d % (id) object name for first found free
    # id and returns (name, id)
    def get_unique_pattern_object_name(phys_space, start_id):
        id = start_id
        name = None
        while True:
            try:
                name = cmputil.derived_object_name(phys_space,
                                                   "_hpm%d" % id)
            except cmputil.CmpUtilException:
                id += 1
            else:
                return (name, id)

    # Return a list of the processors which have some patterns defined
    def cpus_with_patterns_defined():
        all_cpus = get_processors()
        cpus_with_patterns = set()
        for cpu in all_cpus:
            cpu_arch = cpu.iface.processor_info.architecture()
            for (pname, parch, ptarget_list) in hypersim_patterns:
                if (cpu_arch == parch
                    and ((ptarget_list == None)
                         or (cpu.classname in ptarget_list))):
                    cpus_with_patterns.add(cpu)
        return cpus_with_patterns


    # Go though all CPUs that have some pattern defined for them
    hpm_cpus = {}

    all_hpms = {} # Dict of pattern-matchers with memory-space as key
    for o in all_hypersim_pattern_matchers():
        all_hpms[o.memory_space] = o

    for cpu in cpus_with_patterns_defined():
        # Check that there is a pattern matcher for the phys-space
        phys_space = (getattr(cpu, "shared_physical_memory", None)
                      or cpu.iface.processor_info.get_physical_memory())
        if phys_space == None:
            continue
        id = 0
        if phys_space.queue == None:
            phys_space.queue = cpu.queue

        if phys_space in all_hpms:
            pm = all_hpms[phys_space]
        else:
            name = cmputil.derived_object_name(phys_space, "_hpm")
            pm = SIM_create_object("hypersim-pattern-matcher", name,
                                   [["memory_space", phys_space]])
            all_hpms[phys_space] = pm
            if verbose:
                print(("Creating hypersim pattern matcher '%s' " +
                       "attached to '%s'") % (
                    name, phys_space.name))
            (name, id) = get_unique_pattern_object_name(phys_space, id)

        # Install all valid patterns (for arch and cpu type)
        cpu_has_pattern = False

        for (pname, parch, ptarget_list) in hypersim_patterns:
            classes = [s.classname for s in pm.patterns]
            if pname in classes:
                if verbose:
                    print(("Already installed pattern %s for %s"
                           % (pname, phys_space.name)))
                cpu_has_pattern = True
                continue

            if (cpu.iface.processor_info.architecture == None
                or cpu.iface.processor_info.architecture() != parch):
                if verbose:
                    print(("ignoring pattern %s for %s (wrong architecture %s)"
                           ) % (pname, phys_space.name, parch))
                continue

            if ((ptarget_list != None)
                and (cpu.classname not in ptarget_list)):
                if verbose:
                    print(("ignoring pattern %s for %s (wrong processor)"
                           ) % (pname, phys_space.name))
                continue

            if verbose:
                print("Adding pattern %s to %s" % (pname, phys_space.name))
            (name, id) = get_unique_pattern_object_name(phys_space, id)
            obj = SIM_create_object(SIM_get_class(pname), name,
                                    [["pattern_matcher", pm]])
            # Make sure patterns do not get checkpointed
            VT_set_object_checkpointable(obj, False)
            cpu_has_pattern = True

        # Pattern-matcher now populated with patterns
        # Keep track of which CPUs are associated with which pattern-matcher
        if pm in hpm_cpus:
            if cpu_has_pattern:
                hpm_cpus[pm].append(cpu)
        else:
            if cpu_has_pattern:
                hpm_cpus[pm] = [cpu]
            else:
                hpm_cpus[pm] = []

    # Set the CPUs attribute for the hypersim pattern matcher so it knows which
    # cpus it monitors
    for pm in hpm_cpus:
        pm.cpus = hpm_cpus[pm]
    return list(hpm_cpus.keys())

new_command("enable-hypersim", enable_hypersim_cmd,
            args = [arg(flag_t, "-v"),
                    arg(flag_t, "-no-auto"),
                    arg(flag_t, "-no-pattern-matching")],
            type  = ["Performance"],
            short = "enable hypersimulation",
            doc = """
Enable hypersimulation.

Hypersimulation is the ability of the simulator to detect that a loop
is only waiting for something to happen without actually doing
anything, and that it is possible to skip forward in time immediately
to the next interesting event (such as a timer interrupt).

Single-instruction loops (an instruction that jumps to itself) can
often be detected by the processor model itself; this detection is
always enabled.

Some simple loops can be detected during JIT compilation of the target
software. This feature is only supported for some processor architectures.
This detection is normally enabled, but can be turned off with the
<tt>-no-auto</tt> flag.

More complicated loops can be detected using the
hypersim-pattern-matcher module which uses hand-written
specifications, hypersim classes, that describe the structure of the
loops and how to simulate them correctly. Hypersim classes are
specific to processor architectures and target software.
By enabling hypersimulation, all hypersim classes are connected to
matching processors in the configuration. To disable the pattern-matcher
the <tt>-no-pattern-matching</tt> flag can be used.

Enable verbose mode with the flag <tt>-v</tt>.
The command returns the names of the used hypersim-pattern-matcher objects.""")



def disable_hypersim_cmd(verbose):
    disable_hpm(verbose)
    auto_hyper(enable = False, verbose = verbose)
    disable_hypersim()

new_command("disable-hypersim", disable_hypersim_cmd,
            args = [arg(flag_t, "-v")],
            short = "disable hypersimulation",
            doc = """
Disable hypersimulation.

Enable verbose mode with the flag <tt>-v</tt>.""")

def list_hypersim_cmd(used):
    l = []
    for (pname, parch, ptarget_list) in hypersim_patterns:
        info = [pname, parch]
        if ptarget_list:
            s = ""
            for p in ptarget_list:
                s += p + " "
            info.append(s)
        else:
            info.append('Any')
        if (used):
            pm = ""
            for o in all_hypersim_pattern_matchers():
                classes = [s.classname for s in o.patterns]
                if pname in classes:
                    pm += o.name + " "
            if pm != "":
                info.append(pm)
            else:
                info.append("None")
        l.append(info)

    title = ['Name', 'Architecture', 'Processor types']
    if (used):
        title.append("Pattern matchers")
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in title])]
    tbl = table.Table(props, l)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, l)

new_command("list-hypersim-patterns", list_hypersim_cmd,
            args = [arg(flag_t, "-u")],
            type  = ["Performance"],
            short = "list available hypersim patterns",
            doc = """
List the available hypersim-pattern classes. If this command is used in an
expression it returns a list.

With the <tt>-u</tt> flag is also displayed which hypersim-pattern-matcher
that currently uses the pattern.
""")

def all_hypersim_pattern_matchers():
    classname = "hypersim-pattern-matcher"
    if classname in SIM_get_all_classes():
        return list(SIM_object_iterator_for_class(classname))
    else:
        # Passing the class name to SIM_object_iterator_for_class will
        # implicitly load the module. If the module is not loaded,
        # there can be no instances so it's unnecessary to load the
        # module.
        return []

# Returns a dict: {phys_space: ffwd_steps} representing how many
# steps which has been fast-forwarded for each physical memory-space
# containing CPUs which has used autohyper.
def auto_hyper_status(verbose):
    # Automatically found hypersim loops (by the CPUs)
    auto_stat = {}
    physmem = {}
    for cpu in get_processors():
        if not hasattr(cpu, "auto_hyper_loops"):
            continue
        if cpu.auto_hyper_loops == []:
            continue

        for l in cpu.auto_hyper_loops:
            ffwd_steps, pa, precond = l

            if ffwd_steps == 0 and not verbose:
                continue

            if cpu.physical_memory not in physmem:
                physmem[cpu.physical_memory] = [(
                        pa, cpu.name, ffwd_steps, precond)]
            else:
                physmem[cpu.physical_memory].append((
                        pa, cpu.name, ffwd_steps, precond))

    # Sort all loops based in physical address found (per physmem)
    for p in physmem:
        physmem[p].sort()

    if verbose:
        print()
        print("Autohyper detected loops")
        print("========================")
        print()

    for p in physmem:
        if verbose:
            print(p.name)
            print("          ffwd-steps Address       Condition")
        unique_loops = []
        tffwd = 0
        auto_stat[p] = 0
        for i in range(len(physmem[p])):
            (pa, cpu, ffwd, precond) = physmem[p][i]
            tffwd += ffwd
            auto_stat[p] += ffwd
            if i + 1 < len(physmem[p]):
                (npa, _, _, nprecond) = physmem[p][i + 1]
            else:
                (npa, _, _, nprecond) = (-1, 0, 0, "")

            if (pa != npa or precond != nprecond):
                unique_loops.append((tffwd, pa, precond))
                tffwd = 0

        if verbose:
            # Now sort by total ffwd
            unique_loops.sort(reverse=True)
            for l in unique_loops:
                (ffwd, pa, precond) = l
                print("%20d p:0x%08x %s" % (ffwd, pa, precond))

    return auto_stat

# Returns a dict: {phys_space: ffwd_steps} representing how many
# steps which has been fast-forwarded for each physical memory-space associated
# with a pattern-matcher.
def pattern_matcher_status(verbose):
    hpms = all_hypersim_pattern_matchers()
    total_ffwd_idle = 0
    total_ffwd_steps = 0
    classes = []
    used_classes = []
    used_objs = []
    active = 0
    inactive = 0
    hpm_stat = {}
    for hpm in hpms:
        (ffwd_is, ffwd_s) = hpm.total_ffwd_steps
        total_ffwd_idle += ffwd_is
        total_ffwd_steps += ffwd_s

        hpm_stat[hpm.memory_space] = (ffwd_is + ffwd_s)

        for (p_obj, p_name, p_r_list, _, _, _) in hpm.pattern_info:
            if p_obj.classname not in classes:
                classes.append(p_obj.classname)
            for (r_paddr, r_active, r_c_list) in p_r_list:
                if r_active:
                    active += 1
                else:
                    inactive += 1
            if len(p_r_list) > 0:
                used_objs.append((p_obj, p_name))
                if p_obj.classname not in used_classes:
                    used_classes.append(p_obj.classname)
    if verbose:
        classes.sort()
        used_classes.sort()
        print("Hypersim patterns installed on: %d memory spaces" % (len(hpms)))
        print("Total active patterns:          %d" % (active))
        print("Total inactive patterns:        %d" % (inactive))
        print("Total ffwd idle steps:          %d" % (total_ffwd_idle))
        print("Total ffwd steps:               %d" % (total_ffwd_steps))
        print("Installed patterns classes:")
        for c in classes:
            print("     %s" % c)
        print("Used patterns classes:")
        if not used_classes:
            print("     None")
        for c in used_classes:
            print("     %s" % c)
        print("Used pattern objects:")
        if not used_objs:
            print("     None")
        for (obj, name) in used_objs:
            print("     %s : object %s" % (name, obj.name))
        print()
        # Run status cmd on all hypersim pattern matchers
        for p in hpms:
            print()
            run_command("%s.status" % (p.name))

    return hpm_stat

# Collect the amount of hypersim recorded by the CPU
def cpu_hyper_status():
    cpu_stat = {}
    for cpu in SIM_get_all_processors():
        if not hasattr(cpu.iface, "step_info"):
            continue
        physmem = (getattr(cpu, "shared_physical_memory", None)
                   or cpu.iface.processor_info.get_physical_memory())
        if not physmem:
            continue

        ffwd = cpu.iface.step_info.get_halt_steps()
        if physmem in cpu_stat:
            cpu_stat[physmem] += ffwd
        else:
            cpu_stat[physmem] = ffwd
    return cpu_stat


def hypersim_status_cmd(verbose):
    global hypersim_enabled
    if not hypersim_enabled:
        print("hypersim currently not enabled")
        print()

    hpm_stat = pattern_matcher_status(verbose)
    auto_stat = auto_hyper_status(verbose)
    cpu_stat = cpu_hyper_status()

    # Combine the three dicts to a new one:
    # {physmem, [cpu-ffwd, hpm-ffwd, auto-ffwd]}
    total_stat = {}
    for physmem in cpu_stat:
        total_stat[physmem] = [cpu_stat[physmem], 0, 0]

    for physmem in hpm_stat:
        if physmem in total_stat:
            cpu_ffwd = total_stat[physmem][0]
        else:
            cpu_ffwd = 0
        total_stat[physmem] = [cpu_ffwd, hpm_stat[physmem], 0]

    for physmem in auto_stat:
        if physmem in total_stat:
            cpu_ffwd = total_stat[physmem][0]
            hpm_ffwd = total_stat[physmem][1]
        else:
            cpu_ffwd = 0
            hpm_ffwd = 0
        total_stat[physmem] = [cpu_ffwd, hpm_ffwd, auto_stat[physmem]]

    total_ffwd_cpu = 0
    total_ffwd_pm = 0
    total_ffwd_auto = 0
    print()
    print("Hypersim Status Summary")
    print("=======================")
    for physmem in total_stat:
        print(physmem.name)
        print("\tcpu handled ffwd-steps:     %15d" % (total_stat[physmem][0]))
        print("\tpattern-matcher ffwd-steps: %15d" % (total_stat[physmem][1]))
        print("\tautohyper ffwd-steps:       %15d" % (total_stat[physmem][2]))
        total_ffwd_cpu += total_stat[physmem][0]
        total_ffwd_pm += total_stat[physmem][1]
        total_ffwd_auto += total_stat[physmem][2]

    print()
    print("Total cpu handled ffwd-steps:     %17d" % (total_ffwd_cpu))
    print("Total pattern-matcher ffwd-steps: %17d" % (total_ffwd_pm))
    print("Total autohyper ffwd-steps:       %17d" % (total_ffwd_auto))
    print("Total ffwd-steps:                 %17d" % (
        total_ffwd_cpu + total_ffwd_pm + total_ffwd_auto))

new_command("hypersim-status", hypersim_status_cmd,
            args = [arg(flag_t, "-v")],
            type  = ["Performance"],
            short = "show hypersim status",
            doc = """
Show status overview for hypersimulation. With the <tt>-v</tt> all
&lt;hypersim-pattern-matcher&gt;.status commands are executed also with more
detailed information.""")

# Enable hypersim by default for non-stall execution
enable_hypersim()
enable_hpm(verbose = False)
ah_enabled = True
