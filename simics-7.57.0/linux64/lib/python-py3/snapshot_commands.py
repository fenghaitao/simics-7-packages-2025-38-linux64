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

import cli
import simics
import table
from cli import (
    CliError,
    arg,
    assert_not_running,
    command_return,
    flag_t,
    get_completions,
    list_t,
    new_command,
    str_t,
)


def snapshot_name_expander(comp):
    s = simics.SIM_list_snapshots()
    return get_completions(comp, s)


def check_error(r):
    if r == simics.Snapshot_Error_No_Error:
        return
    elif r == simics.Snapshot_Error_No_Name:
        msg = "No snapshot name given"
    elif r == simics.Snapshot_Error_Snapshot_Not_Found:
        msg = "Snapshot not found"
    elif r == simics.Snapshot_Error_Snapshot_Already_Exists:
        msg = "Snapshot already exists"
    elif r == simics.Snapshot_Error_Illegal_Configuration:
        msg = "Configuration does not support snapshots"
    elif r == simics.Snapshot_Error_Internal_Error:
        msg = "Internal error"
    else:
        msg = "Unknown error"
    raise CliError(msg)


def find_free_snapshot_name(base):
    existing = set(simics.SIM_list_snapshots())
    i = 0
    while True:
        candidate = f"{base}{i}" if i else base
        if candidate not in existing:
            return candidate
        i += 1


def cmd_take_snapshot(name):
    if not name:
        name = find_free_snapshot_name("snapshot")
    check_error(simics.SIM_take_snapshot(name))
    return name


def cmd_restore_snapshot(name):
    assert_not_running()
    if not name:
        existing = simics.SIM_list_snapshots()
        if len(existing) == 1:
            name = existing[0]
        else:
            raise CliError("No snapshot name given")
    check_error(simics.SIM_restore_snapshot(name))
    return command_return(message=f"Restored snapshot {name}")


def cmd_delete_snapshot(names, all):
    if all and names:
        raise CliError("Can't specify snapshots when deleting all snapshots")
    if all:
        names = simics.SIM_list_snapshots()
    non_existing = set(names) - set(simics.SIM_list_snapshots())
    if non_existing:
        raise CliError("Snapshots not found: " + ", ".join(sorted(non_existing)))
    for name in names:
        check_error(simics.SIM_delete_snapshot(name))


def cmd_list_snapshots(use_steps = True):
    snapshots = simics.SIM_list_snapshots()
    if snapshots:
        columns = [
            [(table.Column_Key_Name, "Name")],
            [(table.Column_Key_Name, "Page Size"),
             (table.Column_Key_Alignment, "right")],
            [(table.Column_Key_Name, "Previous")],
        ]
        props = [(table.Table_Key_Columns, columns)]
        data = []
        for s in sorted(snapshots):
            info = simics.SIM_get_snapshot_info(s)
            page_size = info['pages'] * 8192
            previous = info['previous'] or ""
            data.append([s, page_size, previous])
        tbl = table.Table(props, data)
        output = tbl.to_string(no_row_column = True)
    else:
        output = "No snapshots"
    return command_return(output, snapshots)

new_command("take-snapshot", cmd_take_snapshot,
                        [arg(str_t, "name", "?", None)],
                        type = ["Snapshots"],
                        see_also = ["restore-snapshot", "delete-snapshot",
                                    "list-snapshots"],
                        short = "take a snapshot of the current simulation"
                                " state",
                        doc = """
Take an in-memory snapshot of the current simulation state. Optionally give
the snapshot a <arg>name</arg>. If no name is given the command finds a free
name to use for the snapshot.
""")

new_command("restore-snapshot", cmd_restore_snapshot,
                        args = [arg(str_t, "name", "?", None,
                                    expander = snapshot_name_expander)],
                        type = ["Snapshots"],
                        see_also = ["take-snapshot", "delete-snapshot",
                                    "list-snapshots"],
                        short = "restore the simulation state from an in-memory"
                                " snapshot",
                        doc = """
Restore the state of the simulation from an in-memory snapshot with the given
<arg>name</arg>. If no name is given and there is just one snapshot,
that snapshot is restored.
""")

new_command("delete-snapshot", cmd_delete_snapshot,
                        args = [arg(str_t, "names", "*", [],
                                    expander = snapshot_name_expander),
                                arg(flag_t, "-all", "?", False)],
                        type = ["Snapshots"],
                        see_also = ["take-snapshot", "restore-snapshot",
                                    "list-snapshots"],
                        short="delete in-memory snapshots of the simulation"
                              " state",
                        doc = """
Delete one or more in-memory snapshots with the specified <arg>names</arg>.
If the <tt>-all</tt> flag is specified all snapshots are deleted.
""")

new_command("list-snapshots", cmd_list_snapshots,
                        args = [],
                        type = ["Snapshots"],
                        see_also = ["take-snapshot", "restore-snapshot",
                                    "delete-snapshot"],
                        short = "list in-memory snapshots of the simulation"
                                " state",
                        doc = """
List in-memory snapshots of the simulation state.
Returns the list of snapshot names. If run interactively it prints the
snapshots as a table.
""")
