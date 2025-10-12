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

import collections
import json
import datetime
import platform
import probes
import psutil
import os

import cli
import conf
import simics_common
import sim_commands
from simics import *

from . import sampler
from . import presentation
from . import logwindow
from . import html_report

class probe_monitor_base(sampler.probe_sampler):
    __slots__ = ("summary", "window", "print_no_samples", "output_file_name")

    cls = confclass(parent=sampler.probe_sampler.cls)

    cls.attr.summary(
        "b",
        default=True,
        doc="Print a summary when simulation stops.")
    cls.attr.window(
        "b",
        default=False,
        doc="Open an independent console window.")
    cls.attr.print_no_samples(
        "b",
        default=False,
        doc="Disable sample printing.")
    cls.attr.output_file_name(
        "n|s",
        default=None,
        doc="Table dump file name.")

    @cls.finalize
    def finalize_instance(self):
        super().finalize_instance()

        log_win = logwindow.LogWindow(self.obj) if self.window else None
        self.presentation = presentation.TablePresentation(
            self, log_win, not self.print_no_samples, self.summary,
            self.output_file_name)

    @cls.iface.table
    def properties(self):
        return self.presentation.build_table_properties(include_hidden=True)

    @cls.iface.table
    def data(self):
        return self.presentation.get_data_history(include_hidden=True)

    def _build_json_host_dict(self):
        sim = conf.sim
        (system, node, _, version, machine, _) = platform.uname()
        hv_info = CORE_host_hypervisor_info()
        hypervisor = ("no" if not hv_info.is_hv_detected else
                      (hv_info.vendor or "an unknown hypervisor detected"))
        cpu_brand = CORE_host_cpuid_brand_string()
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        cpu_freqs = list({x.max for x in psutil.cpu_freq(True)})
        return {
            "name": node,
            "CPU brand": cpu_brand,
            "CPU cores":  cpu_cores,
            "CPU logical cores":  cpu_logical,
            "CPU max freqs": cpu_freqs,
            "memory": sim_commands.abbrev_size(sim.host_phys_mem),
            "IPv4_address": sim.host_ipv4,
            "IPv6 address": sim.host_ipv6,
            "OS": system,
            "OS architecture": machine,
            "OS release": simics_common.os_release(),
            "OS version": version,
            "hypervisor": hypervisor,
        }

    def _build_json_simics_dict(self):
        sim = conf.sim
        threading_mode = cli.global_cmds.set_threading_mode()
        tds = cli.global_cmds.list_thread_domains(_a=True)
        thread_domains = []
        for i in range(len(tds)):
            td_objs = ",".join([o.name for o in tds[i]])
            thread_domains.append([f"TD{i}", td_objs])

        return {
            "simics-revisions": cli.global_cmds.version(),
            "Thread limit": sim.max_threads if sim.max_threads else "Unlimited",
            "Worker threads limit": sim.actual_worker_threads,
            "Simulation threads limit": conf.sim.num_threads_used,
            "Threading mode": threading_mode,
            "Thread domains": thread_domains,

            # Core-sha
            # TS-CPU-sha
        }

    def _build_json_probes_dict(self):
        probes_dict = collections.OrderedDict()
        for sp in self.presentation.select_sprobes(
                include_hidden=True, include_no_sampling=True):
            obj = sp.probe_proxy.prop.owner_obj
            owner = obj.name
            clsname = obj.classname
            module = ",".join(VT_get_all_implementing_modules(clsname))
            value = sp.actual_value()
            cf = probes.CellFormatter(max_lines=5,
                                      ignore_column_widths=True)
            cell_value = sp.probe_proxy.table_cell_value(value, cf)
            fmt_value = sp.probe_proxy.format_value(value, cf)
            sampling_mode = f"-{sp.mode}" if sp.mode != "delta" else ""
            probes_dict[sp.get_unique_id()] = {
                # sampler properties
                "mode": sp.mode,
                # probe-properties
                "kind": f"{sp.probe_proxy.prop.kind}{sampling_mode}",
                "owner": owner,
                "classname": clsname,
                "module": module,
                "type": sp.probe_proxy.prop.type,
                "categories": sp.probe_proxy.prop.categories,
                "display_name": sp.probe_proxy.prop.display_name,
                "desc": sp.probe_proxy.prop.desc,
                "definition": sp.probe_proxy.prop.definition,
                "percent": sp.probe_proxy.prop.percent,
                "float_decimals": sp.probe_proxy.prop.float_decimals,
                "metric": sp.probe_proxy.prop.metric,
                "unit": sp.probe_proxy.prop.unit,
                "binary": sp.probe_proxy.prop.binary,
                "time_fmt": sp.probe_proxy.prop.time_fmt,
                "width": sp.probe_proxy.prop.width,
                # Probe data
                "raw_sample_history": sp.get_history(),
                "final_value": value,
                "final_value_cell": cell_value,
                "final_value_fmt": fmt_value,
            }
        return probes_dict


    def _build_json_target_dict(self, workload):
        try:
            cpu_list = cli.global_cmds.list_processors(_all=True)
            cpu_summary = cli.global_cmds.list_processors_summary(_all=True)
        except cli.CliError:
            cpu_list = []
            cpu_summary = []

        named_cpu_list = [[obj.name, cls, freq, cell.name, scheduled]
                          for (obj, _, cls, freq, cell, scheduled) in cpu_list]
        return {
            "workload": workload,
            "CPU summary": cpu_summary,
            "CPUs": named_cpu_list,
            "probes": self._build_json_probes_dict(),
        }

    def create_json_dict(self, workload):
        now = datetime.datetime.now()
        date_str = now.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
        return {
            "contents": "Simics Probe Data",
            "version": 1.0,
            "date": date_str,
            "host": self._build_json_host_dict(),
            "simics": self._build_json_simics_dict(),
            "target": self._build_json_target_dict(workload)
        }


    def export_to_json(self, workload, indent):
        d = self.create_json_dict(workload)
        if indent:
            return json.dumps(d, indent=4)
        return json.dumps(d)

    def merge_json(self, in_files, truncate_samples):
        sections = [
            "contents",
            "version",
            "date",
            "host",
            "simics",
            "target",
            "flamegraph",
        ]

        # Fill the dict with the contents of the first file
        with open(in_files[0], "r") as f:
            js = json.load(f)

        for fn in in_files[1:]:
            with open(fn, "r") as f:
                d = json.load(f)

            # Copy sections verbatim if they are not already included
            for s in sections:
                if (not s in js) and (s in d):
                    js[s] = d.pop(s)

            if "target" in d and "probes" in d["target"]:
                for k in js["target"]["probes"]:
                    if k in d["target"]["probes"]:
                        print(f"Replacing {k}")
                js["target"]["probes"].update(d["target"]["probes"])

            if "flamegraph" in d:
                js["flamegraph"].update(d["flamegraph"])

        # Make sure the number of samples are the same in the merged
        # json file. If the simulation is indeterministic this might
        # not be the case.
        sample_lengths = [len(v["raw_sample_history"])
                          for k, v in js["target"]["probes"].items()
                          if v["raw_sample_history"]]
        min_samples = min(sample_lengths)
        max_samples = max(sample_lengths)

        if min_samples != max_samples:
            if not truncate_samples:
                raise cli.CliError(
                    "Different amount of samples found in probes"
                    f" min:{min_samples}, max:{max_samples},"
                    "  use -truncate-samples to ignore")

            truncated = []
            for k, v in js["target"]["probes"].items():
                samples = len(v["raw_sample_history"])
                if samples > min_samples:
                    js["target"]["probes"][k]["raw_sample_history"] = (
                        v["raw_sample_history"][0:min_samples])
                    truncated.append(k)

            pn = "\n\t".join(truncated)
            print("WARNING: The amount of samples differs from the merged runs!")
            print("This could be an effect of indeterministic simulation")
            print(f"{len(truncated)} different probes have been truncated from"
                  f" {max_samples} down to {min_samples} samples.")
            print(f"The following probes were truncated:\n\t{pn}")
        return json.dumps(js, indent=4)

    def create_html_report(self, html_dir, json_filename, json_graph, one_page):

        def read_json_file(filename):
            try:
                with open(filename, 'r') as file:
                    try:
                        js = json.load(file)
                    except json.JSONDecodeError as json_err:
                        raise cli.CliError(f"Error decoding JSON: {json_err}")
            except FileNotFoundError:
                raise cli.CliError(f"File not found: {filename}")
            except IOError as io_err:
                raise cli.CliError(f"IO error: {io_err}")
            return js

        if json_filename:
            # Create report for already existing json file
            d = read_json_file(json_filename)
        else:
            # Report for current run
            d = self.create_json_dict("")

        print(f"Reading graph-specification file: {json_graph}")
        gs = read_json_file(json_graph)
        html_report.produce(d, html_dir, gs, one_page)

class probe_monitor(probe_monitor_base):
    __slots__ = ()

    cls = confclass("probe_monitor",
                    parent=probe_monitor_base.cls,
                    pseudo=True,
                    short_doc="probe monitor",
                    doc="Probe sampler and data collector tool that allows user"
                    " to observe collected data.")
