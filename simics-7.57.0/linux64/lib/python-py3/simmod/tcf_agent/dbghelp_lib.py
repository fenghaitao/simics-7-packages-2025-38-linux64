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


import glob
import os
import re
import shutil

import cli
import conf
import simics

def forward_slash(path):
    return path.replace('\\', '/')

def backward_slash(path):
    return path.replace('/', '\\')

def prefix_parenthesis(path):
    return path.replace('(', '\\(').replace(')', '\\)')

def colon_prefix():
    return '' if 'NO_C_COLON' in os.environ else 'C:/'

def intel_sw_tools():
    return f'{colon_prefix()}IntelSWTools'

def program_files_64_bit():
    return f'{colon_prefix()}Program Files'

def program_files_32_bit():
    return f'{colon_prefix()}Program Files (x86)'

def version_sort(version_and_paths):
    return sorted(
        version_and_paths, reverse=True, key=lambda x: x[0])

class DbghelpFinder:
    def __init__(self, top_dir, wildcard, regexp, dll_paths):
        self.top_dir = top_dir
        self.wildcard = wildcard
        self.regexp = regexp
        self.dll_paths = [f'{x}/dbghelp.dll' for x in dll_paths]

    def re_match_for_path(self, path):
        path = forward_slash(path)
        prog_files = prefix_parenthesis(self.top_dir())
        for regexp in [
                f'{prog_files}/{self.regexp}/{x}' for x in self.dll_paths]:
            match = re.match(regexp, path)
            if match:
                return match
        return None

    def best_matching_path(self):
        matches = []
        for wildcard in [f'{self.top_dir()}/{self.wildcard}/{x}' for x in
                         self.dll_paths]:
            for path in glob.glob(wildcard):
                if not os.path.isfile(path):
                    continue
                match = self.re_match_for_path(path)
                if not match:
                    continue
                matches.append([match.group(1), path])
        if not matches:
            return None
        return [x[1] for x in version_sort(matches)][0]

def isd_finder():
    """DbghelpFinder for ISD"""
    return DbghelpFinder(
        intel_sw_tools,
        'system_debugger/*',
        'system_debugger/([0-9]*-[a-z]*)',
        ['system_debug/bin'])

def msvc_finder_vs2022():
    """DbghelpFinder for MSVC 2022 and newer"""
    return DbghelpFinder(
        program_files_64_bit,
        'Microsoft Visual Studio/*/*',
        'Microsoft Visual Studio/([0-9]*)/[a-zA-Z]*',
        ['Common7/IDE/CommonExtensions/Microsoft/TestWindow/VsTest/x64',
         'Common7/IDE/Extensions/TestPlatform/Extensions/Cpp/x64'])

def msvc_finder_vs2017():
    """DbghelpFinder for MSVC 2017 and newer"""
    return DbghelpFinder(
        program_files_32_bit,
        'Microsoft Visual Studio/*/*',
        'Microsoft Visual Studio/([0-9]*)/[a-zA-Z]*',
        ['Common7/IDE/Remote Debugger/x64',
         'Common7/IDE/CommonExtensions/Microsoft/TestWindow/Extensions/Cpp/x64',
         'Common7/IDE/Extensions/TestPlatform/Extensions/Cpp/x64'])

def msvc_finder_vs2015():
    """DbghelpFinder for MSVC 2015 and older"""
    return DbghelpFinder(
        program_files_32_bit,
        'Microsoft Visual Studio *',
        'Microsoft Visual Studio ([0-9.]*)',
        ['Common7/IDE/Remote Debugger/x64'])

def wdk_finder():
    return DbghelpFinder(
        program_files_32_bit,
        'Windows Kits/*',
        'Windows Kits/([0-9.]*)',
        ['Debuggers/x64'])

def finders():
    return [isd_finder(), msvc_finder_vs2022(), msvc_finder_vs2017(),
            msvc_finder_vs2015(), wdk_finder()]

def is_valid_path(path):
    for finder in finders():
        if finder.re_match_for_path(path):
            return True
    return False

def simics_dbghelp_path():
    return simics.SIM_lookup_file('%simics%/win64/lib/dbghelp.dll')

def external_dbghelp_path():
    for finder in finders():
        result = finder.best_matching_path()
        if result:
            return forward_slash(result)
    return None

def dbghelp_path():
    for fun in (simics_dbghelp_path, external_dbghelp_path):
        path = fun()
        if path:
            return path

def copy_dbghelp_cmd(obj, dbghelp_ext_path_in):
    if conf.sim.project is None:
        raise cli.CliError("Failed to find Simics project")

    def simics_proj_dbghelp_path():
        path = f'{conf.sim.project}/win64/lib/dbghelp.dll'
        return path if (os.path.exists(path) and os.path.isfile(path)) else None

    if simics_proj_dbghelp_path():
        raise cli.CliError(
            "Failed to copy dbghelp.dll since it already exists. Please quit"
            f" Simics, and remove {backward_slash(simics_proj_dbghelp_path())}"
            " before retrying")

    if dbghelp_ext_path_in:
        dbghelp_ext_path = dbghelp_ext_path_in
        if not os.path.basename(dbghelp_ext_path_in).lower() == 'dbghelp.dll':
            raise cli.CliError("The provided path to dbghelp.dll"
                " must end with the file 'dbghelp.dll'")
    else:
        dbghelp_ext_path = external_dbghelp_path()

    if dbghelp_ext_path is None:
        raise cli.CliError("Could not find suitable dbghelp.dll")

    proj_lib_path = f'{forward_slash(conf.sim.project)}/win64/lib'
    if not os.path.exists(proj_lib_path):
        try:
            os.makedirs(proj_lib_path)
        except OSError as e:
            raise cli.CliError(f"Failed to create directory '{proj_lib_path}'"
                               f" with error '{e}'")

    dbghelp_proj_path = f'{proj_lib_path}/dbghelp.dll'
    try:
        shutil.copyfile(dbghelp_ext_path, dbghelp_proj_path)
    except IOError as e:
        raise cli.CliError(
            f"Failed to copy dbghelp.dll from '{dbghelp_ext_path}' with error"
            f" '{e}'")

    return cli.command_return(
        message="Successfully copied dbghelp.dll from"
        f" '{backward_slash(dbghelp_ext_path)}' to"
        f" '{backward_slash(dbghelp_proj_path)}'. Please restart Simics to load"
        " dbghelp.dll.")

def add_copy_command():
    cli.new_command("copy-dbghelp", copy_dbghelp_cmd,
                    args = [cli.arg(
                cli.filename_t(dirs=False), 'dbghelp-path', '?')],
                    cls = "tcf-agent",
                    short = "copy dbghelp.dll into project",
                    doc = """
Copies dbghelp.dll either from <arg>dbghelp-path</arg> if this is provided, or
from a installations of either <tt>Visual Studio</tt> or
<tt>Windows Driver Kit</tt> to the current Simics project under
<file>win64/lib/dbghelp.dll</file>. Note that Simics must be restarted after
dbghelp.dll has been copied.""")
