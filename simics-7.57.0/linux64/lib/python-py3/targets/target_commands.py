# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import os
import pathlib
import sys
from . import script_params
from . import sim_params
import simics
import table
from . import targets
import yaml
from .script_commands import preview_name

#
# -------------------- list-targets --------------------
#

# Return description from target script file
def get_target_desc(script_file: str):
    try:
        data = sim_params.parse_script(script_file)
    except script_params.TargetParamError as ex:
        print(ex, file=sys.stderr)
        return "<parse error>"
    else:
        return data['desc']

# Return string and target list, suitable for CLI command.
# Also used by command line options.
def list_targets(substr, verbose, border_style=None, presets=False):
    rows = []
    target_list = []
    if presets:
        data = sim_params.get_preset_list()
    else:
        data = sim_params.get_target_list()
    for (t, info) in data.items():
        if substr in t:
            row = [t, info['pkg']]
            if verbose:
                row += [str(info['script']), get_target_desc(info['script'])]
            rows.append(row)
            target_list.append(t)

    header = ["Target" if not presets else "Preset", "Package"]
    if verbose:
        header += ["Script", "Description"]
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, n)]
               for n in header])]
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True,
                        border_style=border_style) if rows else ""
    return [msg, target_list]

def list_targets_cmd(substr, verbose):
    [msg, target_list] = list_targets(substr, verbose)
    return cli.command_verbose_return(msg, target_list)

cli.new_command(
    "list-targets", list_targets_cmd,
    args=[cli.arg(cli.str_t, "substr", "?", ""),
          cli.arg(cli.flag_t, "-verbose")],
    type=["CLI", "Files", "Parameters"],
    short="list available targets",
    see_also=["load-target", "list-presets", "<script-params>.list"],
    doc="""
Lists available target systems from the current set of packages as
well as the Simics, and also saved target systems in the project. The
<arg>substr</arg> argument can be used to only display targets whose
names contain the specified sub-string

If <tt>-verbose</tt> is specified, the start script and description
of each target system are displayed.
""")

def list_presets_cmd(substr, verbose):
    [msg, preset_list] = list_targets(substr, verbose, presets=True)
    return cli.command_verbose_return(msg, preset_list)

cli.new_command(
    "list-presets", list_presets_cmd,
    args=[cli.arg(cli.str_t, "substr", "?", ""),
          cli.arg(cli.flag_t, "-verbose")],
    type=["CLI", "Files", "Parameters"],
    short="list available presets",
    see_also=["load-target", "list-targets", "<script-params>.list"],
    doc="""
Lists available presets from the current set of packages as well as the Simics
project. The <arg>substr</arg> argument can be used to only display presets
whose names contain the specified sub-string.

If <tt>-verbose</tt> is specified, the preset file name and preset
description are displayed.
""")

def save_target_cmd(dest, persistent):
    from .sim_params import params

    # save command should not be in the target
    config.cmds.pop()

    # enable-writable-persistent-state creates the directory
    if persistent:
        if not config.collect:
            print("Warning: saving persistent state after simulation started")
        cli.global_cmds.enable_writable_persistent_state(dir=dest)
    else:
        os.makedirs(dest, exist_ok=True)

    data = {"code-type": "simics"}
    if config.scripts:
        target_params = data.setdefault("params", {})
        args = data.setdefault("args", {})
    else:
        target_params = {}
        args = {}

    tree = params.view().tree()
    for (fn, ns) in config.scripts:
        target_params[ns] = {"import": fn}
        args[ns] = script_params.save_parameters(tree[ns])

    lc = pathlib.Path(dest) / 'target'
    with lc.open(mode="w", encoding='utf-8') as f:
        print("@'''\n%YAML 1.2\n---", file=f)
        yaml.dump(data, f)
        print("...\n'''", file=f)
        for l in config.cmds:
            print(l, file=f)
        if persistent:
            print("enable-writable-persistent-state"
                  f"dir={os.path.abspath(dest)}", file=f)

cli.new_tech_preview_command(
    "save-target", preview_name, save_target_cmd,
    args=[cli.arg(cli.filename_t(dirs=True), 'dir'),
          cli.arg(cli.flag_t, "-persistent")],
    type=["CLI", "Files", "Parameters"],
    short="save target",
    see_also=["load-target", "list-targets"],
    doc="""
Save current target system in the directory <arg>dir</arg>.

If <tt>-persistent</tt> is specified, a persistent state is saved with
the target system.
""")

class Target:
    __slots__ = ("cmds", "scripts", "collect")
    def __init__(self):
        self.cmds = []
        self.scripts = []
        self.collect = True
        simics.SIM_hap_add_callback("Core_Continuation",
                                    self._simulation_start, None)

    def add_cmd(self, text):
        if self.collect and not sim_params.is_inside_script():
            self.cmds.append(text)

    def run_cmd(self):
        if self.collect and not sim_params.is_inside_script():
            # Remove explicit run command
            if self.cmds:
                self.cmds.pop()

    def add_script(self, fn, ns):
        if self.collect and not sim_params.is_inside_script():
            if self.cmds and ('load-target' in self.cmds[-1]
                              or 'run-script' in self.cmds[-1]):
                if "namespace" not in self.cmds[-1]:
                    self.cmds[-1] += f" namespace={ns}"
            else:
                self.add_cmd(f"load-target {fn} namespace={ns}")

            self.scripts.append((fn, ns))

    def _simulation_start(self, obj, arg):
        self.collect = False
        simics.SIM_hap_delete_callback("Core_Continuation",
                                       self._simulation_start, None)

# Exposed Python target object
config = None

def init():
    global config
    config = Target()
