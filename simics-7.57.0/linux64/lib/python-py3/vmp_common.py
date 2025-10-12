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


# VMP help functions. setup_vmp is the main entry point and need to be
# stable across minor releases.

import simics, cli, table
from functools import reduce
import unittest
import vmp_constants

# Control VMP acceleration on/off and its timing. Exported to
# hierarchical components.

def setup_vmp(obj, timing, startup, enable):
    assert timing
    assert startup

    setup_vmp_timing(obj)
    vmp_enable(obj, enable, 95)

    return True

def vmp_supported(obj):
    if hasattr(obj.iface, 'vmp'):
        return obj.iface.vmp.class_has_support()
    return False

def vmp_host_support(obj):
    if hasattr(obj.iface, 'vmp'):
        return obj.iface.vmp.host_support()
    return False

def vmp_compatible_config(obj):
    if hasattr(obj.iface, 'vmp'):
        return obj.iface.vmp.compatible_config()
    return False

def vmp_enable(obj, enable, threshold):
    if hasattr(obj.iface, 'vmp'):
        if enable:
            if not obj.iface.vmp.enable():
                return False
            obj.iface.vmp.set_threshold(threshold)
            simics.VT_add_telemetry_data_bool("core.features", "vmp", True)
        else:
            obj.iface.vmp.disable()
        return True
    return False

def vmp_status(obj):
    if hasattr(obj.iface, 'vmp'):
        return obj.iface.vmp.enabled()
    return False

def setup_vmp_via_command(obj, enable, log):
    # check if the CPU modules have VMP support
    if enable and not vmp_supported(obj):
        raise cli.CliError(
            "This CPU model class %s does not support VMP." %
            obj.classname)

    # enable/disable VMP
    if not vmp_supported(obj):
        return False

    if enable and not vmp_compatible_config(obj):
        raise cli.CliError(
            f'The {obj.name} processor has a VMP-incompatible timing.'
            ' Run "setup-x86-timing vmp" to switch to a'
            ' VMP compatible timing model.')

    if not vmp_enable(obj, enable, 95):
        raise cli.CliError("Failed to enable VMP")

    log.append("[%s] VMP %s." % (obj.name, "enabled" if enable else "disabled"))

    return True

def cpu_has_timing_knobs(obj):
    def has_attribute(name):
        return simics.SIM_class_has_attribute(simics.SIM_object_class(obj),
                                              name)
    return (has_attribute("pause_slow_cycles") and
            has_attribute("rdtsc_slow_cycles") and
            has_attribute("port_io_slow_cycles") and
            has_attribute("one_step_per_string_instruction"))

def setup_vmp_timing(obj):
    if not cpu_has_timing_knobs(obj):
        return
    clock_freq = obj.freq_mhz
    obj.pause_slow_cycles = int(clock_freq * 10)
    obj.rdtsc_slow_cycles = int(clock_freq * 10)
    obj.port_io_slow_cycles = int(clock_freq * 10)
    obj.one_step_per_string_instruction = True

    # Select Intel-style 64-bit operation
    if hasattr(obj, "load_far_ptr_64"):
        obj.load_far_ptr_64 = True
        obj.sp_mask_non64 = False
        obj.lar_ldt_lm_invalid = True

    try:
        obj.null_clear_base_and_limit = True
        obj.skip_canonical_logical_check = True
        obj.debug_len_10b_8_bytes = True
        obj.seg_push_zero_pad = False
    except AttributeError:
        # Attributes may not be present on some CPU implementations
        pass

    # Enable DAZ through the MXCSR mask since all VMP-capable host
    # systems will have DAZ and we cannot emulate just FXSAVE
    # (which is used by software to figure out if DAZ is supported
    # or not).
    if hasattr(obj, "mxcsr_mask"):
        if obj.mxcsr_mask:
            # Set the DAZ bit (other bits are kept)
            obj.mxcsr_mask = obj.mxcsr_mask | (1 << 6)
        else:
            # Any non-zero bit means that all bits must be valid,
            # therefore set to support the regular 16 bits in MXCSR.
            obj.mxcsr_mask = 0xffff
    try:
        obj.vm_compatible_config = True
    except AttributeError:
        # Attributes may not be present on some CPU implementations
        pass

def setup_classic_timing(obj):
    # sets up pre-3.0 behaviour
    if not cpu_has_timing_knobs(obj):
        return
    obj.pause_slow_cycles = 0
    obj.rdtsc_slow_cycles = 0
    obj.port_io_slow_cycles = 0
    obj.one_step_per_string_instruction = False
    try:
        obj.init_vm_monitor = False
        obj.vm_compatible_config = False
    except AttributeError:
        # Attributes may not be present on some CPU implementations
        pass

def do_enable_disable_vmp(cpus, enable):
    log = []
    errors = []
    for cpu in cpus:
        try:
            if not setup_vmp_via_command(cpu, enable, log):
                # failed to activate - but we still need to set timing
                enable = False
        except cli.CliError as msg:
            errors.append(str(msg))
            # failed to activate - but we still need to set timing
            enable = False
    if errors:
        raise cli.CliError("\n".join(errors))
    return log

def all_x86_processors():
    return list(simics.SIM_object_iterator_for_interface(["x86"]))

def all_vmp_processors():
    return list(simics.SIM_object_iterator_for_interface(["vmp"]))

class VMP:
    def __init__(self, cpu=None):
        self.cpus = [cpu] if cpu else all_vmp_processors()
    def what(self):
        return "VMP"
    def is_enabled(self):
        enabled = [vmp_status(c) for c in self.cpus]
        if not enabled:
            return cli.BOTH_ENABLED_AND_DISABLED
        elif all(enabled):
            return True
        elif any(enabled):
            return None
        else:
            return False
    def set_enabled(self, enable):
        log = do_enable_disable_vmp(self.cpus, enable)
        self.extra_msg = "\n".join(log)

def cmd_setup_x86_timing_cpu(cpu, timing_model):
    if timing_model == "classic":
        setup_classic_timing(cpu)
    else:
        setup_vmp_timing(cpu)

def cmd_setup_x86_timing(timing_model):
    for cpu in all_x86_processors():
        cmd_setup_x86_timing_cpu(cpu, timing_model)

def vmp_status_cmd(obj):
    if not vmp_supported(obj):
        msg = "VMP is not supported"
        val = False
    elif vmp_status(obj):
        msg = "VMP is enabled"
        val = True
    else:
        msg = "VMP is disabled"
        val = False
    return cli.command_return(message = msg, value = val)

cli.new_command("vmp", vmp_status_cmd,
                [],
                iface = "x86",
                short = "query VMP status",
                type  = ["Performance"],
                see_also = ["enable-vmp", "disable-vmp"],
                doc = """Query if VMP is enabled or not.""")

cli.new_command("enable-vmp", cli.enable_cmd(VMP),
                [],
                iface = "x86",
                short = "enable VMP",
                type  = ["Performance"],
                see_also = ["disable-vmp", "setup-x86-timing"],
                doc = """
Enable VMP for this processor. The command will fail if the processor timing
settings are not VMP compatible. Use <cmd>setup-x86-timing</cmd> to change the
timing settings.

Even when enabled for use with VMP, host acceleration may still not be
engaged due to features being used that cannot be supported with
direct execution. The <cmd>info</cmd> command on the processor will
list the execution mode as VMP if VMP is enabled, and will also show a
reason for VMP not being engaged if such a reason exists.
""")

cli.new_command("enable-vmp", cli.enable_cmd(VMP),
                [],
                short = "enable VMP for all VMP-capable processors",
                type  = ["Performance"],
                see_also = ["disable-vmp", "setup-x86-timing"],
                doc = """
Enable VMP (see <cite>Simics User's Guide</cite>) for all
VMP-capable processors. The command will fail if the processor timing
settings are not VMP compatible. Use <cmd>setup-x86-timing</cmd> to
change the timing settings.

Even when enabled for use with VMP, host acceleration may still not be
engaged due to features being used that cannot be supported with
direct execution. The <cmd>info</cmd> command on the processor will
list the execution mode as VMP if VMP is enabled, and will also show a
reason for VMP not being engaged if such a reason exists.
""")

cli.new_command("disable-vmp", cli.disable_cmd(VMP),
                [],
                iface = "x86",
                short = "disable VMP",
                see_also = ["enable-vmp", "setup-x86-timing"],
                doc = """
Disable VMP for this processor. Its timing settings remain unchanged.""")

cli.new_command("disable-vmp", cli.disable_cmd(VMP),
                [],
                short = "disable VMP for all x86 processors",
                type  = ["Performance"],
                see_also = ["enable-vmp", "setup-x86-timing"],
                doc = """
Disable VMP for all VMP-capable processors. The processor timing settings
remain unchanged""")

cli.new_command("setup-x86-timing", cmd_setup_x86_timing_cpu,
                [cli.arg(cli.string_set_t(["vmp", "classic"]), "model")],
                iface = "x86",
                short = "set timing",
                doc = """
Set the timing parameters for this processor to the given <arg>model</arg>.
The supported models are "vmp" which sets up a VMP-compatible timing
model optimized for interactive use, and "classic" which uses a simple
one-cycle-per-instruction mode. The classic model is not VMP compatible.""")

cli.new_command("setup-x86-timing", cmd_setup_x86_timing,
                [cli.arg(cli.string_set_t(["vmp", "classic"]), "model")],
                short = "set timing for all x86 processors",
                type  = ["Performance"],
                doc = """
Set the timing for all x86 processors to the given <arg>model</arg>.
The supported models are "vmp" which sets up a VMP-compatible timing
model optimized for interactive use, and "classic" which uses a simple
one-cycle-per-instruction mode. The classic model is not VMP compatible.""")

#
# ---------------- VMP features -------------------------------------
#

# Remove the compat code when bumping the API
class VMPFeature:
    @classmethod
    def get(cls, cpu):
        return cpu.iface.vmp.get_feature(cls.feature)
    @classmethod
    def set(cls, cpu, value):
        return cpu.iface.vmp.set_feature(cls.feature, value)

class VMPFeatureEPT(VMPFeature):
    name = 'ept'
    desc = 'Use EPT Paging'
    feature = simics.Vmp_Feature_Ept

class VMPFeatureNestedEPT(VMPFeature):
    name = 'nested_ept'
    desc = 'Use Nested EPT Paging'
    feature = simics.Vmp_Feature_Nested_EPT

class VMPFeatureUG(VMPFeature):
    name = 'unrestricted_guest'
    desc = 'Use Unrestricted Guest Mode'
    feature = simics.Vmp_Feature_Unrestricted_Guest

class VMPFeatureTPR(VMPFeature):
    name = 'tpr_threshold'
    desc = 'Use TPR Threshold'
    feature = simics.Vmp_Feature_Tpr_Threshold

class VMPFeatureBackoff(VMPFeature):
    name = 'backoff'
    desc = 'Use VMP Backoff Mechanism'
    feature = simics.Vmp_Feature_Backoff

class VMPFeatureSVMCS(VMPFeature):
    name = 'shadow_vmcs'
    desc = 'Use Shadow VMCS'
    feature = simics.Vmp_Feature_Shadow_VMCS

class VMPFeatureDirectRdtsc(VMPFeature):
    name = 'direct_rdtsc'
    desc = 'Use Direct RDTSC execution'
    feature = simics.Vmp_Feature_Direct_Rdtsc

class VmpFeatureFiveLevelPaging(VMPFeature):
    name = 'five_level_paging'
    desc = 'Use 5-level paging tables'
    feature = simics.Vmp_Feature_Five_Level_Paging

class VMPFeatureEnabler:
    all_features = {f.name: f for f in [
        VMPFeatureEPT,
        VMPFeatureUG,
        VMPFeatureTPR,
        VMPFeatureBackoff,
        VMPFeatureSVMCS,
        VMPFeatureNestedEPT,
        VMPFeatureDirectRdtsc,
        VmpFeatureFiveLevelPaging
    ]}

    @classmethod
    def string_of_all_features(cls) -> str:
        features = sorted(cls.all_features.keys())
        return ", ".join(features)

    @classmethod
    def what(cls, feature):
        return "VMP feature %s" % feature.name

    @classmethod
    def enable(cls, feature):
        enabled = [feature.set(cpu, True) for cpu in all_vmp_processors()]
        return any(enabled)

    @classmethod
    def disable(cls, feature):
        for cpu in all_vmp_processors():
            feature.set(cpu, False)

    @classmethod
    def is_enabled(cls, feature):
        enabled = [feature.get(cpu) for cpu in all_vmp_processors()]
        if all(enabled):
            return True
        elif any(enabled):
            return None
        else:
            return False

    @classmethod
    def enable_cmd(cls, feature_name):
        if feature_name not in cls.all_features:
            raise cli.CliError("The VMP feature %s is not supported." %
                               feature_name)
        feature = cls.all_features[feature_name]
        if cls.is_enabled(feature):
            msg = "%s already enabled." % cls.what(feature)
        elif cls.enable(feature):
            msg = "%s enabled." % cls.what(feature)
        else:
            msg = ("Failed to enable %s. The feature is not supported." %
                   cls.what(feature))
        return cli.command_return(msg)

    @classmethod
    def disable_cmd(cls, feature_name):
        if feature_name not in cls.all_features:
            raise cli.CliError("The VMP feature %s is not supported." %
                               feature_name)
        feature = cls.all_features[feature_name]
        if cls.is_enabled(feature):
            cls.disable(feature)
            msg = "%s disabled." % cls.what(feature)
        else:
            msg = "%s already disabled." % cls.what(feature)
        return cli.command_return(msg)

    @classmethod
    def expander(cls, base):
        return cli.get_completions(base, cls.all_features.keys())

    @classmethod
    def status(cls):
        for k in sorted(cls.all_features.keys()):
            feature = cls.all_features[k]
            desc = feature.desc
            value = {
                None: "Mixed",
                True: "Enabled",
                False: "Disabled",
            }[cls.is_enabled(feature)]
            print("  %-30s %s" % (desc + ":", value))

cli.new_command("enable-vmp-feature", VMPFeatureEnabler.enable_cmd,
                args=[cli.arg(cli.str_t, "feature",
                              expander=VMPFeatureEnabler.expander)],
                short="enable VMP feature",
                type = ["Performance"],
                doc=f"""
Enable VMP simulation feature. Supported values for <arg>feature</arg>
{VMPFeatureEnabler.string_of_all_features()}
""")

cli.new_command("disable-vmp-feature", VMPFeatureEnabler.disable_cmd,
                args=[cli.arg(cli.str_t, "feature",
                              expander=VMPFeatureEnabler.expander)],
                short="disable VMP feature",
                type = ["Performance"],
                doc=f"""
Disable VMP simulation feature. Supported values for <arg>feature</arg>:
{VMPFeatureEnabler.string_of_all_features()}
""")

cli.new_command("vmp-feature-status", VMPFeatureEnabler.status, args=[],
                short="show VMP feature settings",
                type = ["Performance"],
                doc="Show VMP feature settings.")

#
# ---------------- VMP statistics -------------------------------------
#

class VmpEventNames:
    def __init__(self, kind):
        t = {
            "pctr":     (self._pctrs, "VMXMON_PCTR_"),
            "vmexit":   (self._vmexits, "VMEXIT_"),
            "vmret":    (self._vmrets, "VMRET_"),
            "derived":  (self._derived, "DERIVED_"),
            "turbo":    (self._turbo, "TURBO_"),
        }
        (self._d, self._missing_str) = t[kind]

    def __getitem__(self, ind):
        return self._d.get(ind, "{}{}".format(self._missing_str, ind))

    def keys(self):
        return self._d.keys()

    _vmexits = vmp_constants.vm_exit_codes()
    _vmrets = vmp_constants.vmp_return_codes()

    hardcoded_pctrs = {
        0: "vmx switches",
        1: "userspace switches",
        2: "stepping",
        3: "running",
        4: "#IRQ",
        5: "#NMI",
        6: "#NM",
        7: "#PG",
        8: "#DB",
        9: "#OTHER",
        10: "#FPU_OBTAIN",
        12: "guest #PG",
        11: "get_regs",
        13: "tlb - host PTE missing",
        14: "tlb - host PTE write enable",
        15: "tlb - host PTE other",
        17: "tot cycles",
        18: "sim branches",
        19: "sim steps",
        20: "sim cycles",
        21: "setup cycles",
        22: "entry work cycles",
        23: "timer cycles",
        24: "VMX and trampolines cycles",
        25: "handle timer cycles",
        26: "schedule cycles",
        27: "handle vmexit cycles",
        28: "exception cycles",
        29: "exception #PG cycles",
        35: "return cycles",
        36: "get_regs cycles",
        41: "mapped_limit_prunes",
        42: "dbg1",
        43: "dbg2",
        46: "n_mapped_pages",
        47: "n_locked_pages",
        48: "memory_limit_prunes",
        50: "tlb - new cr3",
        51: "tlb - flush cr3",
        52: "tlb - new segment",
        53: "tlb - verify segment",
        54: "tlb - reuse segment",
        55: "tlb - flush segpage",
        56: "tlb - verify segpage segments",
        57: "tlb - segment dirty flush",
        58: "tlb - segment unlinked",
        59: "tlb - global PTE optimization",
        60: "tlb - flush all",
        61: "tlb - verify level",
        62: "host INVVPID",
        63: "host INVEPT",

        64: "Guest EPT lookup",
        65: "Guest EPT miss",
        66: "Guest EPT nopage",
    }

    _pctrs = vmp_constants.perfctr_codes(hardcoded_pctrs)

    _derived = {
        "inner_loop_it":        "inner loop iterations (avg)",
        "avg_trace":            "average VMX trace (insts)",
        "overhead":             "overhead (%)",
        "kernel_overhead":      "kernel overhead (%)",
        "CPI":                  "host cycles per instruction executed",
        "vmp_utilization":      "VMP utilization (%)",
    }
    _turbo = {
        "vmp_run_steps":              "VMP steps",
        "vmp_emulation_steps":        "VMP emulation steps",
        "vmp_backoff_steps":          "VMP backoff steps",
    }


class VmpStatGroups:
    _groups = (
            ("vmexit", True),
            ("vmret", True),
            # exceptions
            ("pctr", (4, 5, 6, 7, 8, 9, 10)),
            # guest exceptions
            ("pctr", (12, )),
            # vmxmon state
            ("pctr", (19, 46, 47, 62, 63)),
            # tlb
            ("pctr", (13, 14, 15, 50, 51, 52, 53, 54,
                      55, 56, 57, 58, 59, 60, 61)),
            # vmxmon counters
            ("pctr", (0, 1, 2, 3, 11, 48)),
            # cycles
            ("pctr", (17, 18, 20, 21, 22, 23, 24, 25, 26,
                      27, 28, 29, 35, 36, 42, 43)),
            ("pctr", (64, 65, 66)),
            ("derived", True),
            ("turbo", True),
    )
    @classmethod
    def groups(cls):
        return cls._groups

    @classmethod
    def missing_symbols(cls, ctr, index_set):
        in_groups = reduce(
            lambda x, y: x | y,
            (set(v) for (xctr, v) in cls._groups if xctr == ctr), set())
        return (ctr, sorted(set(index_set) - in_groups))

class VmpStatSteps:
    "Class used to track state from last VMP stats reset"
    stamps = {}         # { cpu: VmpStatsReset(cpu) }
    def __init__(self, cpu):
        self.steps = simics.SIM_step_count(cpu)
        self.halt_steps = cpu.iface.step_info.get_halt_steps()
        if cpu in self.stamps:
            s = self.stamps[cpu]
            self.steps -= s.steps
            self.halt_steps -= s.halt_steps

    @classmethod
    def clear(cls, cpu):
        if cpu in cls.stamps:
            del cls.stamps[cpu]
        cls.stamps[cpu] = VmpStatSteps(cpu)


class VmpStatsData:
    def __init__(self, cpu):
        self.cpu = cpu

        (vmexits, pctrs, vmret) = list(cpu.vm_monitor_statistics)
        turbo_keys = VmpEventNames("turbo").keys()
        tcntrs = {x: cpu.turbo_stat[x] for x in turbo_keys}

        vss = VmpStatSteps(cpu)
        self.__stats = {
            "pctr":     dict(enumerate(pctrs)),
            "vmexit":   dict(enumerate(vmexits)),
            "vmret":    dict(enumerate(vmret)),
            "turbo":    tcntrs,
            "nonvmp":   {
                'steps': vss.steps,
                'halt_steps': vss.halt_steps,
            }
        }
        self.__stats["derived"] = self.build_derived_data()

    def build_derived_data(self):
        pctrs = self.__stats["pctr"]
        nonvmp = self.__stats["nonvmp"]
        der = {}

        vmx_switches = pctrs[0]
        userspace_switches = pctrs[1]

        tot_cycles = pctrs[17]
        sim_steps = pctrs[19]
        sim_cycles = pctrs[20]
        kern_cycles = 0
        for i in range(21, 40):
            kern_cycles += pctrs[i]

        total_steps = nonvmp['steps']
        halt_steps = nonvmp['halt_steps']

        for x in VmpEventNames('derived').keys():
            der[x] = 0

        if userspace_switches != 0:
            der['inner_loop_it'] = vmx_switches / userspace_switches
        if vmx_switches != 0:
            der['avg_trace'] = sim_steps / vmx_switches

        if tot_cycles != 0:
            der['overhead'] = (tot_cycles - sim_cycles) / tot_cycles * 100

        if kern_cycles != 0 and sim_cycles != 0:
            der['kernel_overhead'] = ((kern_cycles - sim_cycles)
                                      / kern_cycles * 100)
        if sim_steps != 0 and sim_cycles != 0:
            der['CPI'] = sim_cycles / sim_steps

        if total_steps > halt_steps:
            der['vmp_utilization'] = (sim_steps
                                      / (total_steps - halt_steps) * 100)
        return der

    def __getitem__(self, key):
        return self.__stats[key]

    def clear(self):
        self.cpu.vm_monitor_statistics = [[], [], []]
        for x in VmpEventNames("turbo").keys():
            self.cpu.turbo_stat[x] = 0
        VmpStatSteps.clear(self.cpu)


class VmpStats:
    def __init__(self, cpu = None):
        if isinstance(cpu, list) or isinstance(cpu, tuple):
            cpuset = cpu
        elif cpu == None:
            cpuset = [x for x in simics.SIM_object_iterator(None)
                      if hasattr(x, 'vm_monitor_statistics')]
        else:
            cpuset = [cpu]

        self.data = [VmpStatsData(cpu)
                     for cpu in sorted(cpuset, key=lambda c: c.name)]

    @classmethod
    def stats_cmd(cls, cpu = None):
        return cls(cpu).get_stats()

    def clear(self):
        for x in self.data:
            x.clear()

    @classmethod
    def clear_cmd(cls, cpu = None):
        VmpStats(cpu).clear()

    @staticmethod
    def table_string(tbl):
        # First try using the terminal width
        try:
            msg = tbl.to_string(rows_printed=0, no_row_column=True,
                                border_style='ascii')
        except cli.CliError as ex:
            # Avoid hard error, but include warning message
            msg = tbl.to_string(rows_printed=0, no_row_column=True,
                                border_style='ascii',
                                # Ignore terminal width
                                force_max_width=int(10**100))
            msg += f"\n{ex}\nTry the csv parameter instead."
        return msg

class VmpDetailedStats(VmpStats):
    def get_group(self, group):
        (ptype, indexlist) = group

        if indexlist is True:
            indexlist = set()
            for cpudata in self.data:
                indexlist |= set(cpudata[ptype].keys())

        # extract and sum data
        (totsum, tbl) = (0.0, [])
        for i in indexlist:
            try:
                data = [cpudata[ptype][i] for cpudata in self.data]
            except KeyError:
                data = [0] * len(self.data)

            tot = sum(data)
            if tot != 0:
                tbl.append((tot, VmpEventNames(ptype)[i], data))
                totsum += tot
        if totsum == 0:
            return []

        rows = []
        for (tot, label, data) in sorted(tbl, reverse=True):
            rows.append([label, tot / totsum] + data)
        return rows

    def get_stats(self, csv):
        data = []
        for x in VmpStatGroups.groups():
            data += self.get_group(x)

        n_pctrs = len(self.data[0]['pctr']) if self.data else 0
        data += self.get_group(VmpStatGroups.missing_symbols(
            "pctr", range(0, n_pctrs)))
        props = [(table.Table_Key_Columns,
                  [[(table.Column_Key_Name, "VMP Event")],
                   [(table.Column_Key_Name, "tot %"),
                    (table.Column_Key_Float_Decimals, 2),
                    (table.Column_Key_Float_Percent, True)]]
                  + [[(table.Column_Key_Name, x.cpu.name),
                      (table.Column_Key_Float_Decimals, 2)]
                     for x in self.data])]
        tbl = table.Table(props, data)
        if csv:
            tbl.csv_export(csv)
            msg = f"VMP statistics summary written to {csv}"
        else:
            msg = self.table_string(tbl)
        return cli.command_verbose_return(msg, data)

class VmpStatsSummary(VmpStats):
    def get_stats(self, csv):
        props = [(table.Table_Key_Columns,
                  [[(table.Column_Key_Name, "Processor")],
                   [(table.Column_Key_Name, "Average VMX Trace"),
                    (table.Column_Key_Float_Decimals, 0)],
                   [(table.Column_Key_Name, "VMX Switches")]])]
        data = [[d.cpu.name, d["derived"]["avg_trace"],
                 d["pctr"][0]] for d in self.data]
        tbl = table.Table(props, data)
        if csv:
            tbl.csv_export(csv)
            msg = f"VMP statistics summary written to {csv}"
        else:
            msg = self.table_string(tbl)
        return cli.command_verbose_return(msg, data)

def vmp_stats_cmd_global(summary, csv):
    if summary:
        return VmpStatsSummary().get_stats(csv)
    else:
        return VmpDetailedStats().get_stats(csv)

cli.new_unsupported_command("vmp-stats", "internals", vmp_stats_cmd_global,
                            args=[cli.arg(cli.flag_t, '-s'),
                                  cli.arg(cli.filename_t(), 'csv', '?')],
                            short="print VMP performance statistics",
                            doc="""
Print and return VMP performance statistics.

If the <tt>-s</tt> flag is specified, only a summary is calculated. If
the <arg>csv</arg> filename is specified, the statistics is written to
this file in CSV format.
""")

cli.new_unsupported_command("vmp-stats-clear", "internals", VmpStats.clear_cmd,
                            args=[], short="reset VMP performance statistics",
                            doc="Reset VMP performance statistics.")

cli.new_unsupported_command("vmp-stats", "internals",
                            VmpDetailedStats.stats_cmd,
                            args=[cli.arg(cli.filename_t(), 'csv', '?')],
                            iface="x86",
                            short="show VMP performance statistics",
                            doc="""
Show VMP/VMXMON statistics.

If the <arg>csv</arg> filename is specified, the statistics is written to
this file in CSV format.
""")

cli.new_unsupported_command("vmp-stats-clear", "internals", VmpStats.clear_cmd,
                            args=[], iface="x86",
                            short="clear VMP performance statistics",
                            doc="Clear VMP/VMXMON statistics.")


class TestVMPFeatureEnabler(unittest.TestCase):
    def test_string_of_all_features_contains_classic_feature(self):
        res = VMPFeatureEnabler.string_of_all_features()
        self.assertIn(container=res, member="ept")

    def test_string_of_all_features_separates_with_comma_space(self):
        res = VMPFeatureEnabler.string_of_all_features()
        self.assertIn(container=res, member=", ")

    def test_string_of_all_features_mentions_5_level_paging(self):
        res = VMPFeatureEnabler.string_of_all_features()
        self.assertIn(container=res, member="five_level_paging")


class TestVmpEventNames(unittest.TestCase):
    def all_vm_return_symbols(self):
        stats = VmpEventNames("vmret")
        all_codes = stats.keys()
        return tuple(stats[code] for code in all_codes)

    def all_vm_exit_symbols(self):
        stats = VmpEventNames("vmexit")
        all_codes = stats.keys()
        return tuple(stats[code] for code in all_codes)

    def all_perfctr_symbols(self):
        stats = VmpEventNames("pctr")
        all_codes = stats.keys()
        return tuple(stats[code] for code in all_codes)

    def test_traditional_vmp_return_codes_are_present(self):
        all_vmrets = self.all_vm_return_symbols()
        self.assertIn("VMRET_NOP", all_vmrets)
        self.assertIn("VMRET_CPUID", all_vmrets)
        self.assertIn("VMRET_EXC", all_vmrets)

    def test_range_markers_are_absent(self):
        all_vmrets = self.all_vm_return_symbols()
        self.assertNotIn("VMRET_INST_EXIT_RANGE_START", all_vmrets)
        self.assertNotIn("VMRET_INST_EXIT_RANGE_END", all_vmrets)
        self.assertNotIn("VMRET_COUNT", all_vmrets)

    def test_vm_exit_codes_has_correct_mapping(self):
        stats = VmpEventNames("vmexit")
        self.assertEqual(stats[0], "VMEXIT_EXC")

    def test_vm_exit_range_marker_is_absent(self):
        all_symbols = self.all_vm_exit_symbols()
        self.assertNotIn("VMEXIT_COUNT", all_symbols)

    def test_traditional_perfctr_symbols_are_present(self):
        all_symbols = self.all_perfctr_symbols()
        self.assertIn("vmx switches", all_symbols)
        self.assertIn("userspace switches", all_symbols)

    def test_missed_perfctr_symbol_is_present(self):
        all_symbols = self.all_perfctr_symbols()
        self.assertIn("PERFCTR_TLB_CR3_CHANGE", all_symbols)

    def test_perfctr_range_marker_is_absent(self):
        all_symbols = self.all_perfctr_symbols()
        self.assertNotIn("PERFCTR_COUNT", all_symbols)
