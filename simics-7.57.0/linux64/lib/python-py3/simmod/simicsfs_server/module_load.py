# © 2015 Intel Corporation
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
import re
import cli
import simics
from cli import (
    CliError,
    arg,
    filename_t,
    flag_t,
    get_completions,
    poly_t,
    str_t,
    uint_t,
    )

str_or_uint_t = poly_t("value", str_t, uint_t)

def get_info(obj):
    x,y = obj.protocol
    rows = [("Protocol version", "%d.%d" % (x,y)),
            ("SimicsFS magic", "0x%016x" % obj.magic)]
    return [(None, rows)]

cli.new_info_command('simicsfs_server', get_info)

def get_status(obj):
    mp_rows = [("Pipe", obj.pipe.name if obj.pipe else "None"),
               ("Haps", obj.haps)]
    cl_rows =  [("Clients", len(obj.clients))]
    status = [("Magic pipe", mp_rows), ("SimicsFS", cl_rows)]
    return status

cli.new_status_command('simicsfs_server', get_status)

def _name_ok(s):
    return bool(s) and bool(re.match(r"^[a-zA-Z][0-9a-zA-Z_]*$", s))

def key_expander(string, obj):
    keys = set([k for (_,_,d) in obj.clients for k in d])
    return get_completions(string, list(keys))

def value_expander(string, obj):
    vals = set([v for (_,_,d) in obj.clients for v in list(d.values()) if v])
    return get_completions(string, list(vals))

def group_expander(string, obj):
    grps = [g for g in obj.groups]
    return get_completions(string, grps)

def reqdir_expander(string, obj):
    dirs = set([d for (d,_,_) in obj.rules])
    return get_completions(string, list(dirs))

def destdir_expander(string, obj):
    dirs = set([d for (_,d,_) in obj.rules])
    return get_completions(string, list(dirs))

def _justified_list_dict(d):
    key_w = max([len(k) for k in d] + [7]) + 1
    return "".join(["%*s : %s\n" % (key_w, k, d[k]) for k in sorted(d.keys())])

def list_clients_cmd(obj, key, val):
    clients = []
    ids = []
    for (m,_,d) in obj.clients:
        if key:
            if key not in d:
                continue
            if val:
                if key == "magic" and isinstance(val, int):
                    if m != val:
                        continue
                elif d[key] != val:
                    continue
        clients.append(_justified_list_dict(d))
        ids.append(m)
    return cli.command_verbose_return(value=ids, message="\n".join(clients))

cli.new_command("list-clients", list_clients_cmd,
                args = [
                    arg(str_t, "key", "?", "", expander = key_expander),
                    arg(str_or_uint_t, "value", "?", "",
                        expander = value_expander),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.list-client-groups",
                            "<simicsfs_server>.list-path-rules"],
                short = "list SimicsFS clients",
                doc = """
    List SimicsFS clients and their information. The available information will
    depend on the client.

    The client data is presented as key-value string pairs.

    SimicsFS client version 1.0 will only show up after the first operation is
    performed on the filesystem. For later client versions, mounting the
    filesystem is enough for it to appear on this list.

    It is also possible to list clients by just a <arg>key</arg> or both a
    <arg>key</arg> and <arg>value</arg>, then only the matching clients will be
    listed.  """)

def get_valid_clients_for_group(obj, gdict):
    ids = []
    for (m,_,d) in obj.clients:
        for k in gdict:
            if k in ("clients", "group"):
                continue
            if k not in d:
                break
            gv = gdict[k]
            if k == "magic" and isinstance(gv, int):
                if gv != m:
                    break
            elif d[k] != gv:
                break
        else:
            ids.append(m)
    return ids

def list_client_groups_cmd(obj, group):
    gnames = []
    groups = []
    for grp in obj.groups:
        if group and grp != group:
            continue
        gnames.append(grp)
        gdict = obj.groups[grp].copy()
        clnts = get_valid_clients_for_group(obj, gdict)
        cstr = ", ".join(["0x%016x" % x for x in clnts])
        gdict["clients"] = cstr if clnts else "<none>"
        gdict["group"] = grp
        groups.append(_justified_list_dict(gdict))
    return cli.command_verbose_return(value=sorted(gnames),
                                      message="\n".join(groups))

cli.new_command("list-client-groups", list_client_groups_cmd,
                args = [
                    arg(str_t, "group", "?", "", expander = group_expander),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.add-client-group",
                            "<simicsfs_server>.list-clients",
                            "<simicsfs_server>.list-path-rules",
                            "<simicsfs_server>.remove-client-group"],
                short = "list client groups",
                doc = """
    List client groups.

    A client group is used to select clients for path rules to apply to. A key
    and its value is matched against the client information to determine whether
    a client belongs to the group or not.

    The group will list all matching clients by their magic numbers.

    The <arg>group</arg> argument is used to list the information about that
    particular group.  """)

def add_client_group_cmd(obj, group, key, value):
    if not _name_ok(group):
        raise CliError("Illegal group name: %s" % group)
    if key == "magic" and isinstance(value, int):
        value = "0x%016x" % value
    if not obj.groups:
        obj.groups = {group:{key:value}}
    elif group in obj.groups:
        obj.groups[group][key] = value
    else:
        obj.groups[group] = {key:value}

cli.new_command("add-client-group", add_client_group_cmd,
                args = [
                    arg(str_t, "group", expander = group_expander),
                    arg(str_t, "key", expander = key_expander),
                    arg(str_or_uint_t, "value", expander = value_expander),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.list-client-groups",
                            "<simicsfs_server>.remove-client-group"],
                short = "add client group",
                doc = """
    Add or update a client group.

    The client group with <arg>group</arg> is created or updated with
    <arg>key</arg> and <arg>value</arg>. Repeat the command for the same group
    name to update it with new <arg>key</arg> and <arg>value</arg> arguments or
    change the <arg>value</arg> of an existing <arg>key</arg>.

    The command <cmd class="simicsfs_server">list-clients</cmd> will show the
    possible keys and values of the clients.""")

def remove_client_group_cmd(obj, group, all_flag):
    if not obj.groups:
        raise CliError("No groups exist")
    elif all_flag:
        if group:
            raise CliError("Cannot give both a group name and the -all flag")
        obj.groups = {}
    elif not group:
        raise CliError("Either -all flag or a group name is required")
    elif not _name_ok(group):
        raise CliError("Illegal group name: %s" % group)
    elif group not in obj.groups:
        raise CliError("Group '%s' not found" % group)
    else:
        del obj.groups[group]

cli.new_command("remove-client-group", remove_client_group_cmd,
                args = [
                    arg(str_t, "group", "?", "", expander = group_expander),
                    arg(flag_t, "-all"),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.add-client-group",
                            "<simicsfs_server>.list-client-groups"],
                short = "remove client group",
                doc = """
    Remove a client group.

    The client <arg>group</arg> is removed.

    It is also possible to remove all client groups with the argument
    <tt>-all</tt>.

    At least one argument is required.
    """)

def list_path_rules_cmd(obj, reqdir, destdir, group):
    rules = []
    rvals = []
    for (s, d, g) in obj.rules:
        if reqdir and reqdir != s:
            continue
        if destdir and destdir != d:
            continue
        if group and group != g:
            continue
        rules.append(_justified_list_dict({"reqdir":s, "destdir":d, "group":g}))
        rvals.append([s, d, g])
    return cli.command_verbose_return(value=rvals, message="\n".join(rules))

cli.new_command("list-path-rules", list_path_rules_cmd,
                args = [
                    arg(filename_t(dirs=True, exist=False), "reqdir", "?", "",
                        expander = reqdir_expander),
                    arg(filename_t(dirs=True, exist=False), "destdir", "?", "",
                        expander = destdir_expander),
                    arg(str_t, "group", "?", "", expander = group_expander),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.add-path-rule",
                            "<simicsfs_server>.check-path-rules",
                            "<simicsfs_server>.list-clients",
                            "<simicsfs_server>.list-client-groups",
                            "<simicsfs_server>.remove-path-rule"],
                short = "list path rules",
                doc = """
    List path rules.

    Each path rule is listed with the requested directory (<arg>reqdir</arg>) to
    be replaced with the destination directory (<arg>destdir</arg>) and client
    group, if set.

    The path rules are listed in order of priority, with highest priority first.
    This is the order in which they are matched against the clients, but in two
    sweeps. Where the first sweep is for path rules with a group and the second
    sweep is for path rules without a group. Note that only the first matching
    rule is applied.

    The arguments <arg>reqdir</arg>, <arg>destdir</arg> and <arg>group</arg> may
    be used to filter the listed path rules.  """)

def add_path_rule_cmd(obj, reqdir, destdir, group):
    if group and not _name_ok(group):
        raise CliError("Illegal group name: %s" % group)
    reqdir = os.path.normpath(reqdir)
    destdir = os.path.normpath(destdir)
    obj.rules += [[reqdir, destdir, group]]

cli.new_command("add-path-rule", add_path_rule_cmd,
                args = [
                    arg(filename_t(dirs=True, exist=False), "reqdir"),
                    arg(filename_t(dirs=True, exist=True), "destdir"),
                    arg(str_t, "group", "?", "", expander = group_expander),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.check-path-rules",
                            "<simicsfs_server>.list-path-rules",
                            "<simicsfs_server>.remove-path-rule"],
                short = "add path rule",
                doc = """
    Add a new path rule.

    The path rule will, for matching clients (if <arg>group</arg> is defined),
    replace the requested directory (<arg>reqdir</arg>) with a new
    destination directory (<arg>destdir</arg>) on each access.

    The path rules are matched in the order they were added (oldest first) and
    only the first matching rule is applied.

    The path rule with <arg>reqdir</arg> and <arg>group</arg> is created or
    updated with <arg>destdir</arg>. The <arg>group</arg> defines a subset of
    clients that this rule applies to. If no group name is given, the path rule
    is valid for all clients.  """)

def remove_path_rule_cmd(obj, reqdir, destdir, group, all_flag):
    if group and not _name_ok(group):
        raise CliError("Illegal group name: %s" % group)
    crit = sum([bool(x) for x in [reqdir, destdir, group]])
    if not crit and not all_flag:
        raise CliError("Too few argument")
    reqdir = os.path.normpath(reqdir)
    destdir = os.path.normpath(destdir)
    keep_pr = []
    rm_cnt = 0
    for pr in obj.rules:
        hits = sum([bool(x and x == y) for x, y in
                    zip(pr, [reqdir, destdir, group])])
        if hits < crit:
            keep_pr.append(pr)
        else:
            rm_cnt += 1
    if rm_cnt:
        if rm_cnt > 1 and not all_flag:
            raise CliError("Multiple matches, use -all flag to remove all.")
        obj.rules = keep_pr
    else:
        raise CliError("No matching path rule found. Nothing removed.")

cli.new_command("remove-path-rule", remove_path_rule_cmd,
                args = [
                    arg(filename_t(dirs=True, exist=False), "reqdir", "?", "",
                        expander = reqdir_expander),
                    arg(filename_t(dirs=True, exist=False), "destdir", "?", "",
                        expander = destdir_expander),
                    arg(str_t, "group", "?", "", expander = group_expander),
                    arg(flag_t, "-all"),
                ],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.add-path-rule",
                            "<simicsfs_server>.check-path-rules",
                            "<simicsfs_server>.list-path-rules"],
                short = "remove path rule",
                doc = """
    Remove a path rule.

    The <arg>reqdir</arg> argument is used to select rules by the host
    subdirectory requested by the client.

    The <arg>destdir</arg> argument is used to select rules by the host
    replacement destination subdirectory.

    The <arg>group</arg> argument is used to select rules by a group name.

    The command will only remove a path rule if there is an unique match,
    unless the <tt>-all</tt> flag is given. Enabling that flag will remove all
    the path rules that match the criteria. When the flag is used without any
    other arguments, all rules will be removed.

    At least one argument is required.  """)

def check_path_rules_cmd(obj):
    def add_msg(msglist, s, d, g, reason):
        msgstr = ("WARNING: Path rule %s -> %s"
                  % (s, d))
        msgstr += (" is unenforceable because group %s" % g) if g else ""
        msglist.append("%s %s" % (msgstr, reason))
    msg = []
    groups = dict(obj.groups)
    clients = list(obj.clients)
    cg = dict()
    for g in groups:
        gd = groups[g]
        for c in clients:
            (m,_,cd) = c
            for k in gd:
                if cd[k] != gd[k]:
                    break
            else:
                cv = cg.get(g, [])
                cg[g] = cv + [m]
    for (s, d, g) in obj.rules:
        if not os.path.exists(d):
            add_msg(msg, s, d, None, "destination does not exist")
        elif not os.path.isdir(d):
            add_msg(msg, s, d, None, "destination is not a directory")
        if not g:
            if not clients:
                add_msg(msg, s, d, g, "matches no clients")
        elif g not in groups:
            add_msg(msg, s, d, g, "does not exist")
        elif g not in cg:
            add_msg(msg, s, d, g, "matches no clients")
    return cli.command_return(value=len(msg), message="\n".join(msg))

cli.new_command("check-path-rules", check_path_rules_cmd,
                args = [],
                cls = "simicsfs_server",
                type = ["Files"],
                see_also = ["<simicsfs_server>.add-path-rule",
                            "<simicsfs_server>.list-path-rules",
                            "<simicsfs_server>.remove-path-rule"],
                short = "check path rules",
                doc = """
    Check for obsolete or broken path rules.

    This command is meant to help the user find problems with the path rules. It
    will detect if a path rules matches no clients, or has a broken destination
    path, and give warnings for these cases.

    It does not currently warn about path rules that cannot be reached because a
    prior path rule will always match for a client.  """)
