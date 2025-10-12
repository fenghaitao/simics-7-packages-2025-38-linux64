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
import sys
from pathlib import Path
import itertools
import simics
import conf
from simicsutils import packageinfo
from simicsutils.host import host_type
from simicsutils.internal import simics_base
import cli

# This module manages the package-list globally selected by Simics.
# The purpose of most functions is to expose packageinfo functionality
# to C.

_package_list = None

# List of module paths provided by user through SIMICS_EXTRA_LIB,
# SIM_add_module_dir or --module-path, plus the project's module
# directory. Duplicates are eliminated. Modules in these paths get
# higher priority than paths from installed packages.
_module_user_dirs = None

def py_dir(pkg: str) -> str:
    return str((Path(pkg) / host_type() / "lib" / "python-py3").resolve())

def init_package_list(filename):
    '''Called once on startup'''
    global _package_list
    _package_list = packageinfo.PackageList(filename)

    return package_paths()


def lookup_path_in_packages(path):
    result = _package_list.lookup_path_in_packages(path)
    return str(result) if result else None


def package_paths():
    return list(map(str, _package_list.valid_package_paths))


def prioritized_package_paths():
    return [str(pi.path) for pi in _package_list.packages if pi.prioritized]


def full_version():
    return _package_list.full_version()


def base_version():
    return _package_list.base_version()


def _get_package_info_attr(_):
    return [pi.as_attr() for pi in _package_list.packages]


def _get_package_path_attr(_):
    return package_paths()

def add_module_dir(path: str):
    managed = _managed_sys_path_entries()
    start_index = _find_sublist(sys.path, managed)
    if start_index < 0:
        return False
    path = str(Path(path).resolve())
    if path in _module_user_dirs:
        # ok, ignore
        return True
    _module_user_dirs.append(path)
    updated = _managed_sys_path_entries()
    sys.path[start_index:start_index + len(managed)] = updated
    simics.CORE_set_module_searchpath([os.path.dirname(s) for s in updated],
                                      len(_module_user_dirs))
    return True

def _managed_sys_path_entries():
    return ([os.path.join(p, 'python-py3') for p in _module_user_dirs]
            + [py_dir(p) for p in package_paths()
               if p in prioritized_package_paths()]
            + [py_dir(p) for p in package_paths()
               if p not in prioritized_package_paths()])

def _find_sublist(haystack, needle):
    entries = _managed_sys_path_entries()
    for i in range(len(sys.path)):
        if all(a == b for (a, b) in zip(sys.path[i:], entries)):
            return i
    return -1

def reset_sys_path():
    # This will not remove any duplicates since there aren't any.
    # Duplicates were removed in init_module_searchpath.
    entries = {p: None for p in _managed_sys_path_entries()}
    sys.path = list(entries) + [p for p in sys.path if p not in entries]

def _get_prioritized_packages(_):
    return [pi.package_name for pi in _package_list.packages
            if pi.prioritized]

def _set_prioritized_packages(_, names):
    managed = _managed_sys_path_entries()
    start_index = _find_sublist(sys.path, managed)
    if start_index < 0:
        simics.SIM_attribute_error(
            "sys.path has been tampered with,"
            " use the reset-sys-path command to restore it.")
        return simics.Sim_Set_Illegal_Value
    for name in names:
        if name:
            _package_list.set_prioritized_package(name)
        else:
            _package_list.unset_all_prioritized_packages()
    updated = _managed_sys_path_entries()
    sys.path[start_index:start_index + len(managed)] = updated
    simics.CORE_set_module_searchpath([os.path.dirname(s) for s in updated],
                                      len(_module_user_dirs))
    simics.SIM_module_list_refresh()
    return simics.Sim_Set_Ok


def _get_package_list(_):
    return (None if _package_list.filename is None
            else str(_package_list.filename))

def init_module_searchpath(paths_from_argv):
    global _module_user_dirs
    env_path = os.getenv('SIMICS_EXTRA_LIB')
    dirs = itertools.chain([Path(conf.sim.project) / host_type() / 'lib']
                           if conf.sim.project else [],
                           filter(None, paths_from_argv.split(os.path.pathsep)),
                           filter(None, env_path.split(os.path.pathsep))
                           if env_path else [])
    # remove duplicates
    _module_user_dirs = list({str(Path(d).resolve()): None for d in dirs})
    updated = _managed_sys_path_entries()
    # avoid excess entry
    duplicate = Path(__file__).parent.resolve()
    assert str(duplicate) in updated, (duplicate, updated)
    sys.path = updated + [
        p for p in sys.path
        if not Path(p).exists() or not duplicate.samefile(Path(p))]
    simics.CORE_set_module_searchpath([os.path.dirname(s) for s in updated],
                                      len(_module_user_dirs))

def initialize_packageinfo():
    assert _package_list
    sim = simics.SIM_get_class('sim')
    simics.SIM_register_attribute(
        sim, 'package_info',
        _get_package_info_attr, None,
        simics.Sim_Attr_Pseudo | simics.Sim_Attr_Internal,
        '[[ss|niss|nis|nsisnsbs]*]',
        "List with information about installed packages.")

    simics.SIM_register_attribute(
        sim, 'package_path',
        _get_package_path_attr, None,
        simics.Sim_Attr_Pseudo | simics.Sim_Attr_Internal,
        '[s*]',
        "List of path to packages.")

    simics.SIM_register_attribute(
        sim, 'package_list',
        _get_package_list, None,
        simics.Sim_Attr_Pseudo,
        's|n',
        "Package list file used in this session (if any).")

    simics.SIM_register_attribute(
        sim, 'prioritized_packages',
        _get_prioritized_packages,
        _set_prioritized_packages,
        # NB: while the prioritized_packages is a pseudo attribute we have code
        # that saves it into checkpoints' info section read by
        # VT_get_checkpoint_info. When checkpoints are loaded we restore the
        # attribute from the info section before any modules are loaded and thus
        # improve chances that the modules are loaded from the correct package.
        simics.Sim_Attr_Pseudo | simics.Sim_Attr_Internal,
        '[s*]',
        "List with names of prioritized packages.")

    cli.new_command(
        "reset-sys-path", reset_sys_path, [],
        short="reset Python sys.path",
        type = ["Python"],
        doc = """Reset Python sys.path to include Simics package paths and
        the Simics project, if any.""")
