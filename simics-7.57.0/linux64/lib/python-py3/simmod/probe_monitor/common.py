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


import simics

import probes


def running_in_simics_client():
    return hasattr(simics, "VT_update_session_key")


def listify(seq):
    if not isinstance(seq, list) and not isinstance(seq, tuple):
        return seq
    ret = []
    for s in seq:
        ret.append(listify(s))
    return ret


def parts(k):
    if ":" in k:
        return k.split(":")
    return [None, k]


def get_matching_cli_ids(objects):
    ids = []
    for proxy in probes.get_all_probes():
        [obj, kind] = parts(proxy.cli_id)
        if obj and objects:
            ids.append(proxy.cli_id)
        if kind not in ids:
            ids.append(kind)
    return ids


def prefix_endswith(prefix, string, ends):
    return len(prefix) > 0 and prefix[-1] in ends and string.startswith(prefix)


def is_cli_id_matching(prefix, proxy):
    if proxy.cli_id == prefix:
        return True
    return prefix_endswith(prefix, proxy.cli_id, ".:")


def is_probe_kind_matching(prefix, proxy):
    [_, kind] = parts(proxy.cli_id)
    if kind == prefix:
        return True
    return prefix_endswith(prefix, kind, ".")

# Supports matching:
# a.b.obj:                        - All probes on object
# a.b.obj:part.of.probe_kind.     - All probes beneath this
# a.b.obj:full.name.of.probe_kind - Explicit probe
def get_matching_probes(prefix):
    matching_proxies = []
    for proxy in probes.get_all_probes():
        if is_cli_id_matching(prefix, proxy):
            matching_proxies.append(proxy)
    return matching_proxies

# Supports matching:
# part.of.probe_kind             - All probes regardless of object
# full.name.of.probe_kind        - All probes with this kind
def get_matching_probe_kinds(prefix):
    matching_proxies = []
    for proxy in probes.get_all_probes():
        if is_probe_kind_matching(prefix, proxy):
            matching_proxies.append(proxy)
    return matching_proxies
