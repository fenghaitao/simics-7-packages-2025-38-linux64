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


import cli
from simmod.os_awareness import framework

def load_parameters(obj, filename):
    settings = framework.parameters_from_file(filename)
    [ok, msg] = obj.iface.osa_parameters.set_parameters(settings)
    if not ok:
        raise cli.CliError("Unusable tracker configuration (%s): %s"
                           % (filename, msg))

def add_load_parameters_cmd():
    cli.new_command(
        'load-parameters', load_parameters,
        [cli.arg(cli.filename_t(simpath=True), 'file')],
        iface = 'osa_parameters', type = ['Debugging'],
        short = 'load tracker parameter settings',
        see_also = ['<osa_parameters>.save-parameters',
                    '<osa_parameters>.supports-parameters'],
        doc = """
Load configuration parameters for a software tracker from a file. The
<arg>file</arg> argument should point to the file containing the parameters
configuration.

To <tt>create</tt> a tracker <tt>configuration parameter</tt> file, refer to the
documentation of the software tracker that will be used (typically the tracker
inserted with command <cmd class="os_awareness">insert-tracker</cmd>). Usually
software tracker component and class have a <tt>detect-parameters</tt> command
which can be used to create a <tt>configuration parameter</tt> file. To find the
<tt>detect-parameters</tt> command, issue
<nobr><cmd>apropos detect-parameters</cmd></nobr> in the Simics CLI. """)

def save_parameters(obj, filename, no_children, overwrite):
    [ok, params] = (
        obj.iface.osa_parameters.get_parameters(not no_children))
    if not ok:
        raise cli.CliError(params)
    [tracker_name, parameters] = params

    try:
        framework.save_parameters_file(
            filename, tracker_name, parameters, overwrite)
    except framework.FrameworkException as e:
        raise cli.CliError("Failed to save file: %s" % e)

def add_save_parameters_cmd():
    cli.new_command('save-parameters', save_parameters,
                    [cli.arg(cli.filename_t(), 'file'),
                     cli.arg(cli.flag_t, '-no-children'),
                     cli.arg(cli.flag_t, '-overwrite')],
                    iface = 'osa_parameters',
                    see_also = ['<osa_parameters>.load-parameters',
                                '<osa_parameters>.supports-parameters'],
                    short = "save parameters",
                    doc = """
Save the current configuration parameters to a file.

The <arg>file</arg> argument points to the file that should be written. If the
<tt>-overwrite</tt> argument is given any existing file will be overwritten.

The <tt>-no-children</tt> argument can be used to exclude parameters of child
trackers, this is only meaningful for stacked trackers with guests, such as
Hypervisor trackers. """)

def supports_parameters(obj, filename):
    [kind, _] = framework.parameters_from_file(filename)
    res = obj.iface.osa_parameters.is_kind_supported(kind)
    return cli.command_return(
        value = res,
        message = 'Parameters of kind %s are%s supported by %s'
        % (kind, '' if res else ' not', obj.name))

def add_supports_parameters_cmd():
    cli.new_command('supports-parameters', supports_parameters,
                    [cli.arg(cli.filename_t(simpath=True), 'file')],
                    iface = 'osa_parameters',
                    see_also = ['<osa_parameters>.load-parameters',
                                '<osa_parameters>.save-parameters'],
                    short = "check if supported",
                    doc = """
Returns TRUE if the parameters in <arg>file</arg> are of a type supported by
this tracker. This does not guarantee that the parameters are valid and can
actually be set, as they may still be broken, or not match the software that is
running on the target. """)

def add():
    add_load_parameters_cmd()
    add_save_parameters_cmd()
    add_supports_parameters_cmd()
