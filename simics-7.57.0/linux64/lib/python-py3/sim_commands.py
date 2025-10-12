# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# This module needs to be imported once in order to register the updaters.

import updaters

# Import all other command files

# We import everything from commands.py for backward compatibility.
# Additionally, we import everything from cli and simics since this is what
# commands.py used to do. SSM code base expects that sim_commands provides
# many of the symbols from cli and simics; once this is fixed we can try
# to remove these star imports from sim_commands.py.
# fisketur[wildcard-imports]
from cli import *
from simics import *
from commands import *

import alias_command
import component_commands
import debug_commands
import perfanalyze_commands
import recording_commands
import map_commands
import probes.commands
import instrumentation.commands
import table.cmd
import profile_commands
import device_info_cli
import threading_commands
import targets.script_commands
import snapshot_commands
import pcie_commands

# Use star imports for backwards compatibility
from bp_commands import *
from conf_commands import *
from img_commands import *
from log_commands import *
from mem_commands import *
from path_commands import *
from proc_commands import *
from telemetry_commands import *
# for pcie-downstream-port
from map_commands import map_cmd
# For CPU modules
from profile_commands import register_aprof_views
# For some SSM modules
from map_commands import add_map_cmd, map_match, swap_expander
