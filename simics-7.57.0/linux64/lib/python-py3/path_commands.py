# © 2023 Intel Corporation
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

import cli
import simics
import conf
import table

from sim_commands import (
    package_expander,
)

from simics import (
    SIM_VERSION_5,
    SIM_VERSION_6,
    SIM_VERSION_7,

    Column_Key_Alignment,
    Column_Key_Float_Decimals,
    Column_Key_Footer_Sum,
    Column_Key_Hide_Homogeneous,
    Column_Key_Int_Grouping,
    Column_Key_Int_Pad_Width,
    Column_Key_Int_Radix,
    Column_Key_Metric_Prefix,
    Column_Key_Name,
    Table_Key_Columns,
    Table_Key_Default_Sort_Column,
)

from cli import (
    addr_t,
    arg,
    bool_t,
    filename_t,
    flag_t,
    float_t,
    int16_t,
    int64_t,
    int_t,
    integer_t,
    list_t,
    nil_t,
    obj_t,
    poly_t,
    range_t,
    sint32_t,
    sint64_t,
    str_t,
    string_set_t,
    uint16_t,
    uint64_t,
    uint_t,
    new_command,
    new_unsupported_command,
    new_operator,
    new_info_command,
    new_status_command,
    CliError,
    Markup,
    command_quiet_return,
    command_return,
    command_verbose_return,
)

#
# -------------- simics-path commands ----------------
#

def add_directory_cmd(path, prepend):
    try:
        simics.SIM_add_directory(path, prepend)
    except simics.SimExc_General as ex:
        if cli.interactive_command() or simics.SIM_get_verbose():
            print("Warning: %s" % ex)

new_command("add-directory", add_directory_cmd,
            [arg(filename_t(dirs = 1, keep_simics_ref = 1), "path"),
             arg(flag_t, "-prepend")],
            type = ["Configuration", "Files"],
            short = "add a directory to the Simics search path",
            see_also = ["list-directories", "clear-directories"],
            doc = """
Adds a directory to the Simics search path. The Simics search path is
a list of directories where Simics searches for additional files when
loading a configuration or executing a command like
<cmd>load-file</cmd>.

The value of <arg>path</arg> is normally appended at the end of the
list. If the <tt>-prepend</tt> flag is given, the path will be added as
first in the list.
""")

def list_directories_cmd():
    dirs = simics.SIM_get_directories()
    if not dirs:
        return command_verbose_return(
            'The current Simics search path is empty.', [])

    msg = "The current Simics search path is:"
    for dir in dirs:
        msg += f"\n   {dir}"
    return command_verbose_return(msg, [d for d in dirs])

new_command("list-directories", list_directories_cmd,
            [],
            type = ["Files"],
            short = "list directories in Simics search path",
            see_also = ["add-directory", "clear-directories"],
            doc = """
Lists all directories in the Simics search path.
""")

def clear_directories_cmd():
    simics.SIM_clear_directories()
    print("Simics search path is now empty.")

new_command("clear-directories", clear_directories_cmd,
            [],
            type = ["Files"],
            short = "clear the Simics search path",
            see_also = ["add-directory", "list-directories"],
            doc = """
Empty the Simics search path.
            """)


def lookup_file_cmd(filename, query, error_msg):
    found, file = cli.expand_path_markers(filename)
    if found:
        return os.path.realpath(file)
    message = "Not in search path: '%s'" % filename
    if error_msg != None:
        message += "\n%s" % error_msg
    if query:
        return command_return(message = message, value = False)
    else:
        if error_msg != None:
            # When error message is given a quiet error is raised so that
            # no traceback will be shown.
            raise cli.CliQuietError(message)
        else:
            raise CliError(message)

new_command("lookup-file", lookup_file_cmd,
            [arg(str_t, "filename"), arg(flag_t, "-query"),
             arg(str_t, "error-msg", "?", None)],
            type = ["Files"],
            short = "lookup a filename",
            alias = "resolve-file",
            see_also = ["file-exists", "list-directories"],
            doc = """
Looks for the file or directory <arg>filename</arg> in the Simics
search path, starting with the current working directory. If it is
found, its complete path is returned. If it is not found an error
will be raised unless the <tt>-query</tt> argument is given.

The <tt>-query</tt> argument specifies that the boolean value
<tt>FALSE</tt> is returned when the file is not found instead of
raising an error.

The optional <arg>error-msg</arg> argument adds this string to
the default error message shown when the file is not found. It
also suppresses the backtrace normally shown when an error is
raised.

If <arg>filename</arg> starts with <tt>%simics%</tt>, the rest of the path is
looked up first in the Simics project, and then in all configured Simics
packages. For more information on the <tt>%simics%</tt> or <tt>%script%</tt>
path markers, see the <cite>Simics User's Guide</cite>.""")

def file_exists_cmd(filename):
    found, real_file = cli.expand_path_markers(filename)
    if found:
        message = "File found: '%s'" % os.path.realpath(real_file)
    else:
        message = "Not in search path: '%s'" % filename
    return command_return(message, value = found)

new_command("file-exists", file_exists_cmd,
            [arg(str_t, "filename")],
            type = ["Files"],
            short = "check if a file exists in the search path",
            see_also = ["lookup-file"],
            doc = """
Looks for the file or directory <arg>filename</arg> in the Simics search path,
starting with the current working directory. Returns true if the file is found
and false if not.
""")

def native_path_cmd(filename):
    return simics.SIM_native_path(filename)

new_command("native-path", native_path_cmd,
            [arg(str_t, "filename")],
            type = ["Files"],
            short = "convert a filename to host native form",
            doc = """
Converts a path to its host native form. On Linux, this command returns
<arg>filename</arg> unchanged. On Windows, it translates Cygwin-style paths
to native Windows paths. Refer to the documentation
<fun>SIM_native_path()</fun>, for a detailed description of the conversions
made.

This command can be used for portability when opening files residing on the
host filesystem.
""")

# Finds the package that a script file belongs to, returning its name or None
def find_script_package():
    path = os.path.abspath(cli.resolve_script_path('%script%'))
    old_path = ''
    tail = '-' + conf.sim.host_type
    while path != old_path:
        pi_path = os.path.join(path, "packageinfo")
        if os.path.exists(pi_path):
            all_files = os.listdir(pi_path)
            pi_files = [x for x in all_files if x.endswith(tail)]
            if pi_files:
                return pi_files[0].split(tail)[0]
        old_path = path
        path = os.path.dirname(path)
    return None

def set_prioritized_package_cmd(current, package, clear):
    if clear and (current or package):
        raise CliError('Both -clear flag and other argument(s) given')
    if current and package:
        raise CliError('Both -current flag and package argument supplied')
    if clear:
        conf.sim.prioritized_packages = [""]
        return
    if current:
        if cli.interactive_command():
            raise CliError('-current flag used outside of script')
        package = find_script_package()
        if not package:
            # not an error, but still good to tell user about the no-op
            print("No current package found to mark as prioritized.")
            return
    elif not package:
        raise CliError('No package specified')
    conf.sim.prioritized_packages += [package]
    if not package in conf.sim.prioritized_packages:
        raise CliError('No package "%s"' % package)

new_command("set-prioritized-package", set_prioritized_package_cmd,
            [arg(flag_t, "-current"),
             arg(str_t, "package",  "?", None, expander = package_expander),
             arg(flag_t, "-clear"),],
            type = ["Modules"],
            short = "mark package as prioritized",
            see_also = ['list-prioritized-packages', 'load-module'],
            doc = """
Mark a Simics package, with the name <arg>package</arg>, as prioritized.
When a module to be loaded is found in several packages, the one from a
prioritized package takes precedence over the modules found in non-prioritized
packages. This priority mechanism overrides the default behavior of selecting
the most recently built module. Modules found in user-added search paths and
in the project directory still have higher priority than modules from packages.

For scripts distributed in a package, the <tt>-current</tt> flag can be used
instead of a name to mark the package they belong to as prioritized.

Using the <tt>-clear</tt> flag will empty the list of prioritized packages.""")

def list_prioritized_packages_cmd():
    ret = conf.sim.prioritized_packages
    out = "\n".join(ret)
    return command_verbose_return(message = out, value = ret)

new_command("list-prioritized-packages", list_prioritized_packages_cmd,
            [],
            type = ["Modules"],
            short = "list packages marked as prioritized",
            see_also = ['set-prioritized-package', 'load-module'],
            doc = """
Print or return a list of packages marked as prioritized.""")

def pkg_path_info(p, prio):
    return {'path': p[9],
            'name': p[0],
            'pkg_num': '%d%s' % (p[2], prio),
            'version': p[3],
            'build_id': '%d' % p[5],
            'namespace': p[11],
            'description': p[13]
    }

def search_path_data(p):
    return [p['pkg_num'],  p['name'], p['version'], p['description'],
            f"{p['namespace']}:{p['build_id']}", p['path']]

def list_packages_cmd(sort_name):
    # Pkgs, sorted by package number or name.
    # but sorting by number allows to have Simics base package listed first:
    if sort_name:
        pkgs = sorted(conf.sim.package_info, key = lambda p: p[0])
        data = ([pkg_path_info(p, "") for p in pkgs])
    else:
        pkgs = sorted(conf.sim.package_info, key = lambda p: p[2])
        # Prioritized packages first
        data = ([pkg_path_info(p, " *") for p in pkgs if p[12]]
                + [pkg_path_info(p, "") for p in pkgs if not p[12]])

    ret = [search_path_data(p) for p in data]
    header = ["Pkg", "Name", "Version", "Description", "Build ID", "Path", ]
    properties = [(Table_Key_Columns, [[(Column_Key_Name, h)] for h in header])]
    tbl = table.Table(properties, ret)
    return command_verbose_return(
        message = tbl.to_string(rows_printed=0, no_row_column=True),
        value = ret)

new_command("list-packages", list_packages_cmd,
            [arg(flag_t,"-n")],
            type = ["Modules"],
            short = "list package info in search path order",
            doc = """
Print or return package info in %simics% search path order.

If a package has been prioritized, a star is printed next to the package
number. Use <tt>-n</tt> to sort by name.""")

def list_simics_search_paths_cmd():
    from command_file import simics_paths
    ret = simics_paths()
    out = "\n".join(ret)
    return command_verbose_return(message = out, value = ret)

new_command("list-simics-search-paths", list_simics_search_paths_cmd,
            [],
            type = ["Modules", "Files"],
            short = "return %simics% search paths",
            doc = """
Print or return paths used to resolve %simics%.""")
