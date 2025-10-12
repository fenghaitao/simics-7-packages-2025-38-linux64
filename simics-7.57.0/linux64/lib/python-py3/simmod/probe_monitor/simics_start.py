# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from cli import (new_command, arg, str_t, flag_t, float_t, string_set_t, obj_t,
                 filename_t, get_available_object_name, command_return,
                 global_cmds, CliError, get_completions)
from configuration import *
from simics import *
import conf

import os
from dataclasses import dataclass
from typing import (Optional, Any)

from . import sampler


def enable_probes():
    if not hasattr(conf, "probes"):
        print("Enabling probes")
        global_cmds.enable_probes()


# A base class that helps define the command that creates new sampler-based objects
# and processes the parameters passed to the command.
# Sampler-based classes are built hierarchically, meaning any sampler-based class extends
# another sampler-based class. Eg, the system perfmeter class extends the probe monitor
# class that extends the probe sampler class. An ArgImpl class deals only with
# the parameters specific to a given level in the sampler class hierarchy.
class ArgImpl:
    # Returns a dictionary specifying the command arguments, their documentation,
    # and optionally some properties attached to the command (eg its type and short
    # description).
    # Receives the sampler-based class name as input.
    def kwargs(self, classname):
        return dict(args=[], doc="")

    def arg_num(self):
        return len(self.kwargs("")["args"])

    # Performs any required processing to prepare the creation of a sampler-based object,
    # typically performing checks over the arguments passed to the object creation
    # command.
    # Returns the list of (attribute-name, value) pairs used by the SIM_create_object
    # function to create the sampler-based object.
    # Receives the list of the argument values passed to the command as input.
    def preprocess_args(self, *args):
        return []

    # Performs any required processing after the sampler-based object is created, to finalize
    # its setup.
    # Receives the created sampler-based object and the list of the argument values
    # passed to the command as input.
    def postprocess_args(self, sampler_obj, *args):
        pass


# A class deriving from ArgIml to define and process the parameters specific to
# the base class in the sampler class hierarchy, ie the sampler class itself.
# In addition to the definition and documentation of the arguments passed to the
# command that creates new sampler objects, the dictionary returned by the kwargs
# method includes some other properties that help define the command, typically its
# type and a short description.
class ArgImplForBase(ArgImpl):
    def __init__(self):
        pass

    # Adjusts the name of the sampler-based object that is created.
    def preprocess_name(self, obj_prefix, name):
        return ""


# A class deriving from ArgIml to define and process the parameters specific to any
# classes that can be instantiated in the sampler class hierarchy.
# Some attributes must be passed to the constructor of this class so the command
# that creates new sampler-based objects is properly implemented and documented.
class ArgImplForCreatable(ArgImpl):
    def __init__(self, classname, confclassname, obj_prefix, header_doc, see_also):
        self.classname = classname
        self.confclassname = confclassname
        self.obj_prefix = obj_prefix
        self.header_doc = header_doc
        self.see_also = see_also


class ArgImplChain:
    def __init__(self, base_argimpl, *creatable_argimpls):
        self.base_argimpl = base_argimpl
        self.all_argimpls = [base_argimpl] + list(creatable_argimpls)

    def extract_args_for_argimpl(self, all_args, argimpl_index):
        prev_argimpls = self.all_argimpls[:argimpl_index]
        first_arg_num = sum(prev_argimpl.arg_num() for prev_argimpl in prev_argimpls)
        last_arg_num = first_arg_num + self.all_argimpls[argimpl_index].arg_num()
        return all_args[first_arg_num:last_arg_num]

    def create_cmd(self, cmd_name):
        def _cmd(*all_args):
            final_argimpl = self.all_argimpls[-1]
            obj_prefix = final_argimpl.obj_prefix
            confclassname = final_argimpl.confclassname

            # name is the 1st arg of the base, hence the 1st of all args
            name = all_args[0]
            name = self.base_argimpl.preprocess_name(obj_prefix, name)

            attrs = []
            for (index, argimpl) in enumerate(self.all_argimpls):
                args = self.extract_args_for_argimpl(all_args, index)
                attrs.extend(argimpl.preprocess_args(*args))

            enable_probes()
            try:
                sampler_obj = SIM_create_object(confclassname, name, attrs)
            except (SimExc_General, AttributeError) as e:
                raise CliError(str(e))

            for (index, argimpl) in enumerate(self.all_argimpls):
                args = self.extract_args_for_argimpl(all_args, index)
                argimpl.postprocess_args(sampler_obj, *args)

            return command_return(value=sampler_obj, message=f"Created {sampler_obj.name}")

        def _cmd_kwargs():
            final_impl = self.all_argimpls[-1]
            classname = final_impl.classname
            header_doc = final_impl.header_doc
            see_also = final_impl.see_also

            cmd_kwargs = self.base_argimpl.kwargs(classname)

            cmd_kwargs["args"] = []
            cmd_kwargs["doc"] = ""
            for i in range(len(self.all_argimpls)):
                kwargs = self.all_argimpls[i].kwargs(classname)
                cmd_kwargs["args"] += kwargs["args"]
                cmd_kwargs["doc"] += kwargs["doc"]
            cmd_kwargs["doc"] = header_doc + cmd_kwargs["doc"]
            cmd_kwargs["see_also"] = see_also

            return cmd_kwargs

        new_command(cmd_name, _cmd, **_cmd_kwargs())


def expand_notifier_types(prefix):
    notif_types = [notif[0] for notif in conf.sim.notifier_list]
    return get_completions(prefix, notif_types)


def expand_notifier_objs(notifier_type_arg_idx):
    def expander(prefix, obj, args):
        notifier_type = args[notifier_type_arg_idx]
        if not notifier_type and obj:
            notifier_type = obj.notifier_type
        notif_classes = [notif_class[0]
                        for notif in conf.sim.notifier_list if notifier_type == notif[0]
                        for notif_class in notif[3]]
        notif_objs = [notif_obj.name
                for notif_class in notif_classes
                for notif_obj in SIM_object_iterator_for_class(notif_class)]
        return get_completions(prefix, notif_objs)
    return expander


class SamplerArgImpl(ArgImplForBase):
    def kwargs(self, classname):
        return dict(
            short=f"create new {classname}",
            type=["Probes"],
            args=[arg(str_t, "name", "?"),
                  arg(string_set_t([
                      sampler.REALTIME_SYNC_MODE,
                      sampler.REALTIME_MODE,
                      sampler.VIRTUAL_MODE,
                      sampler.NOTIFIER_MODE,
                      sampler.TIMESTAMP_MODE]),
                      "sampling-mode", "?",
                      sampler.REALTIME_SYNC_MODE),
                  arg(float_t, "interval", "?", 1.0),
                  arg(obj_t("clock", "cycle"), "clock", "?"),
                  arg(str_t, "notifier-type", "?", expander=expand_notifier_types),
                  arg(obj_t("notifier-obj"), "notifier-obj", "?", expander=expand_notifier_objs(
                      notifier_type_arg_idx=4)), # notifier type is the 4th arg in the args list
                  arg(filename_t(), "timestamp-file", "?", None),
                 ],
            doc=f"""

            <b>Argument description:</b>

            Create a new {classname} object with a <arg>name</arg>. If name is not
            given a unique name will be created for it automatically. The
            {classname} samples probes in the system either at a regular interval or
            when a notification is raised.

            The <arg>sampling-mode</arg> argument specifies the mode used to perform
            sampling. Default is "{sampler.REALTIME_SYNC_MODE}" when the interval is in
            realtime (wallclock), but also synchronized so all processor have executed
            at least one quantum since last sample.

            With the "{sampler.REALTIME_MODE}" sampling mode, sampling is
            based on the wallclock time only, without any synchronization.
            Some probes might yield strange results, when some processors
            have not executed at all since the last sample.

            Mode can also be "{sampler.VIRTUAL_MODE}", where
            the virtual time is used to perform sampling. The time is based on the
            virtual time of the first processor found in the system, unless
            <arg>clock</arg> is set to override the default one with another clock
            or processor.

            In "{sampler.REALTIME_SYNC_MODE}", "{sampler.REALTIME_MODE}" and
            "{sampler.VIRTUAL_MODE}" modes the interval is set in seconds by
            the <arg>interval</arg> argument.

            Another available mode is "{sampler.NOTIFIER_MODE}" where sampling is
            performed each time a notification is raised. <arg>notifier-type</arg>
            specifies the notifier type and <arg>notifier-obj</arg> the object where
            the notifier is installed.

            The <arg>timestamp-file</arg> specifies a file to be used recording
            specific timepoints when the sampling should take place.
            Together with {sampler.REALTIME_SYNC_MODE}
            the file will be created and filled with the cycle count from the
            <arg>clock</arg> argument, when the samples are taken.

            With the {sampler.TIMESTAMP_MODE} sampler, this file will instead
            be used as an input file, and the sampling will take place on the
            cycles specified in the file.

            Probes to sample are added by the <tt>&lt;{classname}>.add-probe</tt>
            command.""")

    def preprocess_name(self, obj_prefix, name):
        if not name:
            name = get_available_object_name(obj_prefix)

        if hasattr(conf, name):
            raise CliError(f"An object with name {name} already exists")

        return name

    def preprocess_args(self, name, mode, interval, clock, notifier_type,
                        notifier_obj, timestamp_file):

        if interval < 0:
            raise CliError("interval must be a positive value")

        clock_used = mode in [
            sampler.REALTIME_SYNC_MODE,
            sampler.TIMESTAMP_MODE,
            sampler.VIRTUAL_MODE]

        if clock_used and not clock:
            if SIM_number_processors():
                clock = SIM_get_all_processors()[0]
            else:
                clks = list(SIM_object_iterator_for_interface(["cycle"]))
                clock = clks[0] if clks else None

            if clock:
                print(f"Using {clock.name} as clock")
            else:
                raise CliError(f"Cannot use {mode} sampling:"
                               " No cycle iface in this configuration")

        if mode in [sampler.REALTIME_SYNC_MODE, sampler.REALTIME_MODE] :
            milli_sec = int(interval * 1000.0)
            if milli_sec == 0 or milli_sec > 0xffff:
                raise CliError("real-time time slice must be at"
                               " least 1 ms and less than 65535 ms")

        if mode == sampler.NOTIFIER_MODE:
            if not notifier_type:
                raise CliError("missing notifier type")
            if not notifier_obj:
                raise CliError("missing notifier object")

        if timestamp_file:
            if mode not in [sampler.REALTIME_SYNC_MODE, sampler.TIMESTAMP_MODE]:
                raise CliError(
                    "timestamp-file is only created with"
                    f" '{sampler.REALTIME_SYNC_MODE}' or read with the"
                    f" '{sampler.TIMESTAMP_MODE}' sampler.")

        if mode == sampler.TIMESTAMP_MODE:
            if not timestamp_file:
                raise CliError(
                    "timestamp_file required for the timestamp sampler")

            if not (os.path.isfile(timestamp_file)
                    and os.access(timestamp_file, os.R_OK)):
                raise CliError(
                    f"problems reading timestamp_file: {timestamp_file}")

        return [["mode", mode],
                ["interval", interval],
                ["clock", clock],
                ["notifier_type", notifier_type],
                ["notifier_obj", notifier_obj],
                ["timestamp_file_name", timestamp_file]]


class MonitorArgImpl(ArgImplForCreatable):
    def kwargs(self, classname):
        return dict(
            args=[
                arg(flag_t, "-summary"),
                arg(flag_t, "-window"),
                arg(flag_t, "-print-no-samples"),
                arg(filename_t(), "output-file", "?", None)],
            doc=f"""

            Output handling. By default, each sample measured by the probe-monitor,
            will print a table row on standard output. (A table row can consist of
            multiple lines being printed, including repeated headers).

            The <arg>output-file</arg> argument specifies if the run-time table rows
            should be printed to a file, including any summary output.

            The <tt>-window</tt> switch will cause the run-time samples to be
            printed in a separate console instead of the standard output.

            The <tt>-print-no-samples</tt> switch specifies that no samples are
            printed to standard output, or a window, during execution. Any file
            output, with the <arg>output-file</arg> argument will still occur.

            If <tt>-summary</tt> is given a summary of all sampled probes will be
            printed every time the simulation is stopped.

            The sample data history is also stored in memory, so the data can be
            viewed at any time through the <tt>&lt;{classname}>.print-table</tt>
            command.  When sampling at a high frequency, it is recommended to not
            produce any sample output while running, reducing the overhead of the
            probe-monitor.""")

    def preprocess_args(self, summary, window, print_no_samples,
                        output_file_name):

        if print_no_samples and window:
            raise CliError("-print-no-samples and -window cannot be combined")

        return [["summary", summary],
                ["window", window],
                ["print_no_samples", print_no_samples],
                ["output_file_name", output_file_name]]


class PerfmeterArgImpl(ArgImplForCreatable):
    def kwargs(self, classname):
        return dict(
            args=[
                arg(flag_t, "-mips"),
                arg(flag_t, "-cpu-mips"),
                arg(flag_t, "-exec-modes"),
                arg(flag_t, "-cpu-exec-modes"),
                arg(flag_t, "-cpu-schedule-percent"),
                arg(flag_t, "-cpu-load"),
                arg(flag_t, "-module-profile"),
                arg(flag_t, "-io"),
                arg(string_set_t(
                    [
                        "explore",
                        "performance"
                    ]),
                    "probe-collection", "?", None),
            ],
            doc="""

            The probe-based system perfmeter automatically adds the probes:
            <i>sim.time.virtual</i>, <i>sim.time.wallclock</i> (both session and
            delta).  These show the virtual time and wallclock time spent during the
            simulation.  Note that any time spent when not simulating (standing at
            the Simics prompt), is removed from the wallclock time.

            Further the <i>sim.slowdown</i> delta probe is automatically shown,
            giving the ratio between the virtual time passed compared to the
            wallclock time. That is, a number below 1.0 means the virtual time
            passes faster than the wallclock, a figure of 5.0 means that one virtual
            second takes five wallclock seconds to simulate.

            The <i>sim.process.cpu_percent</i> delta probe shows much much host
            processor usage the Simics process is taking. Any value below 100%
            indicates Simics gets blocked on something, such as real-time mode.  On
            a four processor host, the maximum value would be 400% indicating Simics
            manages to can schedule work on all processors simultaneously.  Note
            that processor usage might be from from other threads, not just the
            execution threads which are used for the actual simulation.

            Finally, the <i>sim.load_percent</i> delta probe, shows an average of
            much actual instructions that is being simulated per cycle. With 100%,
            all simulation time is spent actually executing instructions. Processors
            might also wait for interrupts or other events, when cycles are consumed
            without executing any instructions, reducing this value. This average
            value takes into account how much cycles each processor actually
            consume, so differences in frequencies matter.  Any processor specific
            IPC value (other than 1.0) is also taken into consideration. The IPC
            value may not change during simulation however.

            There are a number of additional flags to easily add more probes to the
            system-perfmeter directly when starting the tool. All of these probes
            shows the <i>delta</i> values, that is, the difference between each
            sample.

            The <tt>-mips</tt> flag adds the <i>sim.mips</i> probe, which reports
            the overall number of instructions per wallclock second being executed.
            Similarly, the <tt>-cpu-mips</tt> adds the <i>cpu.mips</i> probe which
            tells how many instructions per "second", each individual CPU is
            executing, based on the amount of time it is actually scheduled.

            The <tt>-exec-modes</tt> flags adds the
            <i>sim.exec_mode.hypersim_percent</i>, <i>sim.exec_mode.vmp_percent</i>,
            <i>sim.exec_mode.jit_percent</i>, and the
            <i>sim.exec_mode.interpreter_percent</i> probes. These report the
            summary of which execution modes all processors have been executed in.

            Similarly, the <tt>-cpu-exec-modes</tt> flag adds the corresponding
            <i>cpu.exec_mode.</i> probes, reporting the execution modes per
            individual processor in the system.

            The <tt>-cpu-schedule-percent</tt> flag adds the
            <i>cpu.schedule_percent</i> probe which reports the percentage of the
            scheduled simulation time spent in the specific processors. Processors
            with high percentage simulates more slowly.

            The <tt>-cpu-load</tt> flag adds the <i>cpu.load_percent</i> which gives
            the individual load on each processor. See above for the description of
            the <i>sim.load_percent</i> probe.

            The <tt>-module-profile</tt> flag adds the <i>sim.module_profile</i>
            probe which gives a low overhead performance profile of in which shared
            objects the execution is spent.

            The <tt>-io</tt> flag adds the <i>sim.io_intensity</i> probe, reporting
            how frequently IO operations occurs, as number of executed instructions
            per detected IO operation. High values are good, low values could cause
            performance reductions.

            The <arg>probe-collection</arg> specifies a shortcut name for adding
            suitable probes for given scenario.

            The <tt>explore</tt> collection adds large amount of probes suitable
            for finding possible bottlenecks in the execution performance. Some
            of these probes can however have their own overhead when collecting them.
            The large amount of probes collected also impose some overhead.

            The <tt>performance</tt> collection adds a few probes just to measure
            the performance of Simics, without much overhead.

            These are just some generally useful switches for adding probes easily
            directly when creting the system-perfmeter.  Once system-perfmeter
            object has been created, it is possible to remove existing probes or add
            other probes to the sampling.""")

    def postprocess_args(self, perfmeter_obj, mips_probe, cpu_mips_probe,
                         exec_mode_probe, cpu_exec_mode_probe,
                         cpu_schedule_percent_probe, cpu_load_percent_probe,
                         module_profile_probe, io_probe, probe_collection):

        # Help class to specify which probes to enable with properties
        @dataclass
        class SP:
            name : str
            mode : Optional[str] = "delta"
            hidden: Optional[bool] = False
            no_sampling: Optional[bool] = False

        # Default probes
        probes = [
            # Session probes
            SP("sim.time.virtual", mode="session"),
            SP("sim.time.wallclock", mode="session"),

            # Delta probes
            SP("sim.time.virtual"),
            SP("sim.time.wallclock"),
            SP("sim.slowdown"),
            SP("sim.process.cpu_percent"),
            SP("sim.load_percent"),
        ]

        # Add probes based on user switches
        if mips_probe:
            probes += [SP("sim.mips")]

        if cpu_mips_probe:
            probes += [SP("cpu.mips")]

        if exec_mode_probe:
            probes += [
                SP("sim.exec_mode.hypersim_percent"),
                SP("sim.exec_mode.vmp_percent"),
                SP("sim.exec_mode.jit_percent"),
                SP("sim.exec_mode.interpreter_percent")]

        if cpu_exec_mode_probe:
            probes += [
                SP("cpu.exec_mode.hypersim_percent"),
                SP("cpu.exec_mode.vmp_percent"),
                SP("cpu.exec_mode.jit_percent"),
                SP("cpu.exec_mode.interpreter_percent")]

        if cpu_schedule_percent_probe:
            probes += [SP("cpu.schedule_percent")]

        if cpu_load_percent_probe:
            probes += [SP("cpu.load_percent")]

        if module_profile_probe:
            probes += [SP("sim.module_profile")]

        if io_probe:
            probes += [SP("sim.io_intensity")]

        if probe_collection == "explore":
            # Huge amount of probes, don't display these on each sample
            # table-output would be too wide and it would take time
            # to print it out.
            probes += [
                SP("sim.mips"),
                SP("sim.exec_mode.hypersim_percent",hidden=True),
                SP("sim.exec_mode.vmp_percent",hidden=True),
                SP("sim.exec_mode.jit_percent",hidden=True),
                SP("sim.exec_mode.interpreter_percent",hidden=True),
                #
                SP("sim.exec_mode.hypersim_steps",hidden=True),
                SP("sim.exec_mode.vmp_steps",hidden=True),
                SP("sim.exec_mode.jit_steps",hidden=True),
                SP("sim.exec_mode.interpreter_steps",hidden=True),

                SP("sim.vmp.vmexits.total",hidden=True),
                SP("sim.vmp.disabled_reason",hidden=True),

                SP("cpu.schedule_percent",hidden=True),
                SP("cpu.mips",hidden=True),

                SP("cpu.load_percent",hidden=True),
                SP("cpu.load_sim_percent",hidden=True),
                SP("cpu.exec_mode.hypersim_percent",hidden=True),
                SP("cpu.exec_mode.vmp_percent",hidden=True),
                SP("cpu.exec_mode.jit_percent",hidden=True),
                SP("cpu.exec_mode.interpreter_percent",hidden=True),
                SP("cpu.exec_mode.hypersim_steps",hidden=True),
                SP("cpu.exec_mode.vmp_steps",hidden=True),
                SP("cpu.exec_mode.jit_steps",hidden=True),
                SP("cpu.exec_mode.interpreter_steps",hidden=True),
                SP("cpu.vmp.vmexits.total",hidden=True),
                SP("cpu.vmp.disabled_reason",hidden=True),

                # Histograms (with delta values we find useful)
                SP("sim.module_profile",hidden=True),
                SP("sim.vmp.vmexits.histogram",hidden=True),
                SP("sim.time.schedule_object_histogram",hidden=True),

                # Memory related, current values (not delta)
                SP("sim.image.memory_usage", mode="current", hidden=True),
                SP("sim.process.memory.resident", mode="current", hidden=True),
                SP("host.memory.used", mode="current", hidden=True),
                SP("host.swap.used", mode="current", hidden=True),

                # Probes which we just present the final value of
                SP("cpu.esteps", no_sampling=True),
                SP("cpu.vmp.esteps_per_vmexit", no_sampling=True),
                SP("cpu.event.cycle.triggered", no_sampling=True),
                SP("cpu.event.step.triggered", no_sampling=True),
                SP("sim.io_access_class_histogram", no_sampling=True),
                SP("sim.event.cycle.histogram", no_sampling=True),
                SP("sim.interface.lookup_histogram", no_sampling=True),
                SP("sim.attribute.read_histogram", no_sampling=True),
                SP("sim.process.thread_group_histogram", no_sampling=True),
                SP("sim.time.schedule_class_histogram", no_sampling=True),
                SP("sim.probe_sampler.samples.time", no_sampling=True),

                # CPU internal stuff
                SP("cpu.turbo.used_code_area", mode="current", hidden=True),  # Module

                SP("cpu.turbo.threshold_reached", hidden=True),
                SP("cpu.turbo.inserted_blocks", hidden=True),
                SP("cpu.turbo.trampolines", hidden=True),
                SP("cpu.turbo.rejected_blocks", hidden=True),

                SP("cpu.turbo.exit_block_event", hidden=True),
                SP("cpu.turbo.exit_callout_event", hidden=True),
                SP("cpu.turbo.exit_chain_miss", hidden=True),
                SP("cpu.turbo.exit_event_absolute", hidden=True),
                SP("cpu.turbo.exit_event_zero", hidden=True),
                SP("cpu.turbo.exit_pistc_miss", hidden=True),
                SP("cpu.turbo.exit_pistc_not_turbo", hidden=True),
                SP("cpu.turbo.exit_precondition", hidden=True),
                SP("cpu.turbo.exit_prologue_event", hidden=True),
                SP("cpu.turbo.exit_return_on_page", hidden=True),

                # Icode
                SP("cpu.counter.icode.decode", hidden=True),
                SP("cpu.counter.icode.rebind", hidden=True),
                SP("cpu.counter.icode.page_invalidate", hidden=True),
                SP("cpu.counter.icode.remove_all", hidden=True),

                # Executing slow-paths (various cache misses)
                SP("cpu.counter.dstc.miss", hidden=True),
                SP("cpu.counter.pistc.miss", hidden=True),
                SP("cpu.counter.longjmp", hidden=True),
                SP("cpu.counter.page_cache.miss", hidden=True),
            ]
            # Only add cell probes if we have more than one cell
            num_cells = len(list(SIM_object_iterator_for_class("cell")))
            if num_cells > 1:
                probes += [
                    SP("cell.schedule_percent",hidden=True),
                    SP("cell.time.schedule_object_histogram",hidden=True),
                    SP("cell.time.schedule",hidden=True),

                    SP("cell.vmp.disabled_reason",hidden=True),
                    SP("cell.mips",hidden=True),
                    SP("cell.exec_mode.hypersim_percent",hidden=True),
                    SP("cell.exec_mode.vmp_percent",hidden=True),
                    SP("cell.exec_mode.jit_percent",hidden=True),
                    SP("cell.exec_mode.interpreter_percent",hidden=True),

                    SP("cell.exec_mode.hypersim_steps",hidden=True),
                    SP("cell.exec_mode.vmp_steps",hidden=True),
                    SP("cell.exec_mode.jit_steps",hidden=True),
                    SP("cell.exec_mode.interpreter_steps",hidden=True),
                ]

        elif probe_collection == "performance":
            probes += [
                SP("sim.mips"),
                SP("sim.process.cpu_usage_percent", no_sampling=True),
            ]

        for p in probes:
            perfmeter_obj.cli_cmds.add_probe(
                _verbose=False,
                _hidden=p.hidden, _no_sampling=p.no_sampling,
                probe_kind=[p.name], probe=[], mode=p.mode)


class StreamerArgImpl(ArgImplForCreatable):
    def kwargs(self, classname):
        return dict(
            args=[
                arg(filename_t(), "csv-output-file", "1"),
                arg(flag_t, "-no-metadata"),
                arg(flag_t, "-no-timestamp"),
                arg(str_t, "timestamp-probe", "?", None)
            ],
            doc="""

            The <arg>csv-output-file</arg> argument specifies the path of the CSV
            file where the samples are dumped.

            The <tt>-no-metadata</tt> switch disables the insertion of the metadata
            fields in the generated CSV.

            The <tt>-no-timestamp</tt> switch disables the insertion of the timestamp column
            in the generated CSV.

            The <arg>timestamp-probe</arg> allows the user to specify the probe used for
            timestamping, overriding the default timestamp probe selection.""")

    def preprocess_args(self, csv_output_file_name, no_metadata, no_timestamp,
                        timestamp_probe):

        if no_timestamp and timestamp_probe:
            raise CliError(
                "-no-timestamp and timestamp-probe cannot be combined")

        return [["csv_output_file_name", csv_output_file_name],
                ["metadata_enabled", not (no_metadata)],
                ["timestamping", not (no_timestamp)],
                ["timestamp_probe", timestamp_probe]]


monitor_classname = "probe-monitor"
monitor_confclassname = "probe_monitor"
monitor_obj_prefix = "pm"
monitor_header_doc = """The probe-monitor is a tool for sampling probes
during execution and inspecting the collected data manually.
All data is kept in a history and can be exported to CSV or plotted
via Simics-client."""
monitor_create_cmd = "new-probe-monitor"
monitor_see_also = ["new-probe-streamer"]


perfmeter_classname = "system-perfmeter"
perfmeter_confclassname = "probe_system_perfmeter"
perfmeter_obj_prefix = "sp"
perfmeter_header_doc = """The probe-based system-perfmeter is a tool for sampling probes
specifically for looking at Simics performance aspects.
The tool extends the probe-monitor, sharing the same commands and features.
Compared to the probe-monitor, some default probes are automatically used.
There are also handy flags which can be used when creating the tool
to more easily subscribe on additional performance related probes."""
perfmeter_create_cmd = "new-system-perfmeter"
perfmeter_see_also = ["new-probe-streamer", "new-probe-monitor"]


streamer_classname = "probe-streamer"
streamer_confclassname = "probe_streamer"
streamer_obj_prefix = "ps"
streamer_header_doc = """The probe-streamer is a tool for sampling probes
during execution and storing the collected data into a CSV file.
This is useful for batch runs when the data should be used later.
No probe data is saved in the tool, making it useful for collecting
large datasets."""
streamer_create_cmd = "new-probe-streamer"
streamer_see_also = ["new-probe-monitor"]


sampler_argimpl = SamplerArgImpl()
monitor_argimpl = MonitorArgImpl(monitor_classname, monitor_confclassname,
                                 monitor_obj_prefix, monitor_header_doc, monitor_see_also)
perfmeter_argimpl = PerfmeterArgImpl(perfmeter_classname, perfmeter_confclassname,
                                     perfmeter_obj_prefix, perfmeter_header_doc, perfmeter_see_also)
streamer_argimpl = StreamerArgImpl(streamer_classname, streamer_confclassname,
                                   streamer_obj_prefix, streamer_header_doc, streamer_see_also)

monitor_argimpl_chain = ArgImplChain(sampler_argimpl, monitor_argimpl)
perfmeter_argimpl_chain = ArgImplChain(
    sampler_argimpl, monitor_argimpl, perfmeter_argimpl)
streamer_argimpl_chain = ArgImplChain(sampler_argimpl, streamer_argimpl)

monitor_argimpl_chain.create_cmd(monitor_create_cmd)
perfmeter_argimpl_chain.create_cmd(perfmeter_create_cmd)
streamer_argimpl_chain.create_cmd(streamer_create_cmd)
