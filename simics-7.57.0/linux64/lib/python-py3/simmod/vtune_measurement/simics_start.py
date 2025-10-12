# © 2019 Intel Corporation
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
import cli_impl
import simics

cli.add_unsupported('vtune-measurement')

def new_vtune_measurement(name, vtune_path):
    name = cli_impl.new_object_name(name, 'vtune')
    if vtune_path:
        if not os.path.isdir(vtune_path):
            raise cli.CliError("Error: Not a valid directory:%s" % (vtune_path))
        attrs = [["vtune_path", vtune_path]]
    else:
        attrs = []

    try:
        obj = simics.SIM_create_object("vtune_measurement", name, attrs)
    except simics.SimExc_General as msg:
        raise cli.CliError("Cannot create %s: %s" % (name, msg))

    msg = "Created %s" % (obj.name)
    if vtune_path:
        simics.SIM_log_info(
            1, obj, 0, "Use the 'save-preferences' command to save the path"
            " for VTune in further sessions.")
    return cli.command_return(message = msg, value = obj)

cli.new_unsupported_command(
    'new-vtune-measurement', 'vtune-measurement',
    new_vtune_measurement,
    args = [cli.arg(cli.str_t, 'name', '?', None),
            cli.arg(cli.filename_t(exist=True,dirs=True),
                    'vtune-path', '?')],
    type = ['Profiling'],
    short = 'create a vtune session',
    doc = """
    Create an object used to launch VTune and connect
    it to the Simics session for performance profiling of Simics itself.

    The <arg>name</arg> argument can be used to select the name of the
    Simics object created. The <arg>vtune-path</arg> argument specifies
    where VTune Profiler is installed, if not specified, it must either
    have been setup earlier, followed by a <cmd>save-preferences</cmd>
    command, or it must be in the standard path.

    Once the object is created, <cmd
    class="vtune_measurement">start</cmd> command can be used to start
    performance measurement using VTune's "hotspots" analyses.  Run
    the simulation that should be measured and issue the <cmd
    class="vtune_measurement">stop</cmd> when finished.

    After stopping the measurement, the <cmd
    class="vtune_measurement">summary</cmd>, <cmd
    class="vtune_measurement">module-profile</cmd> and <cmd
    class="vtune_measurement">profile</cmd> commands can be used to
    see the hotspots. The VTune result is also stored in a directory
    which can used to analyze the result more in depth using the
    <tt>vtune-gui</tt>.""")
