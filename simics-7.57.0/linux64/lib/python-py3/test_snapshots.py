# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import stest
import simics
import difflib


def take_snapshot(name, msg=None):
    stest.expect_equal(simics.SIM_take_snapshot(name), 0, msg)


def restore_snapshot(name, msg=None):
    stest.expect_equal(simics.SIM_restore_snapshot(name), 0, msg)


def delete_snapshot(name, msg=None):
    stest.expect_equal(simics.SIM_delete_snapshot(name), 0, msg)


def check_snapshot_against_config(name):
    simics.SIM_take_snapshot("__temp__")
    config = simics.VT_dump_snapshot("__temp__")
    simics.SIM_delete_snapshot("__temp__")
    snapshot = simics.VT_dump_snapshot(name)
    compare_snapshots(config, snapshot, tofile=name)
    check_snapshot_references(snapshot)


def compare_snapshots(
    config,
    snapshot,
    fromfile="<config>",
    tofile="<snapshot>",
    msg="Difference between snapshots",
):
    if config == snapshot:
        return

    def fmt(s):
        res = []
        for name, cls, attrs, pages in s:
            res.append(f"{name}: {cls} {'{'}")
            for aname, value in attrs:
                # The ftp service does not support snapshots.
                # The tcp_pcbs isn't restored properly, just skip it.
                # See SIMICS-21691
                if cls == "service-node" and aname == "tcp_pcbs":
                    res.append(f"  {aname}: skipping-broken-attribute")
                elif cls == 'x86ex-tlb' and aname == 'tlb':
                    for idx in range(len(value)):
                        if idx == 0:
                            value[idx].sort()
                        else:
                            if len(value[idx]) > 1:
                                value[idx][1:] = sorted(value[idx][1:])
                    res.append(f"  {aname}: {value}")
                else:
                    res.append(f"  {aname}: {value}")
            res.append("")
            for offset, page in pages:
                res.append(f"  {offset}: {page}")
            res.append("}")
        return res

    config = fmt(config)
    snapshot = fmt(snapshot)
    failed = False
    for d in difflib.unified_diff(
        config, snapshot, fromfile=fromfile, tofile=tofile, lineterm=""
    ):
        failed = True
        print(d)
    if failed:
        stest.fail(msg)


def check_snapshot_references(snapshot):
    """No references should point outside the snapshot"""
    objects = {name for (name, _, _, _) in snapshot}
    for oname, cname, attrs, pages in snapshot:
        for aname, value in attrs:
            escaping = attr_references(value) - objects
            if escaping:
                stest.fail(
                    f"Attribute {oname}.{aname} has escaping references {escaping}"
                )


def attr_references(value, acc=None):
    acc = set() if acc is None else acc
    if isinstance(value, list):
        if len(value) == 2 and value[0] == "__snapshot-obj__":
            acc.add(value[1])
        else:
            for e in value:
                attr_references(e, acc)
    elif isinstance(value, dict):
        for k, v in value.items():
            attr_references(k, acc)
            attr_references(v, acc)
    return acc
