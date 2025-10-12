# © 2016 Intel Corporation
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
import simmod.os_awareness as osa
from . import sample_linux_tracker_comp as component
component.sample_linux_tracker_comp.register()

def get_sample_linux_tracker_status(tracker):
    return [(None, [("Enabled", tracker.enabled)])]

def get_sample_linux_tracker_info(tracker):
    return [(None, [("Parent", tracker.parent)])]

def get_sample_linux_mapper_status(mapper):
    return [(None, [("Enabled", mapper.enabled)])]

def get_sample_linux_mapper_info(mapper):
    return [(None, [("Parent", mapper.parent)])]

def add_sample_linux_detect_command(cls, detector):
    cli.new_command(
        'detect-parameters', detector,
        args = [cli.arg(cli.filename_t(), 'param-file', '?', None),
                cli.arg(cli.str_t, 'name', "?", "Linux"),
                cli.arg(cli.flag_t, '-load'),
                cli.arg(cli.flag_t, '-overwrite')],
        cls = cls,
        short = "generate settings for the sample Linux tracker",
        see_also = ['<osa_parameters>.load-parameters'],
        doc = """
Generate parameters for the sample Linux tracker. In a more generic version,
this would have to analyze a symbol file or target memory in order to generate
parameters matching the target software. Detect the parameters to use with the
Linux tracker.

The optional <arg>param-file</arg> argument is used to specify where to save
the parameters, the default is 'detect.params'. If this argument is left out
and the <tt>-load</tt> flag is used then no parameters will be saved.

The optional <arg>name</arg> argument is used to specify the root node name in
the node tree.

The <tt>-load</tt> flag can be used to load the newly detected parameters
directly after detection.

The optional <tt>-overwrite</tt> flag can be used to update the parameter
file, even if it already exists. """)

def save_params(tracker_name, params, filename, overwrite):
    try:
        osa.framework.save_parameters_file(
            filename, tracker_name, params, overwrite)
    except osa.framework.FrameworkException as e:
        raise cli.CliError(str(e))

def set_params(tracker_obj, params):
    tracker_comp = simics.SIM_object_parent(tracker_obj)
    try:
        osa.framework.set_parameters(tracker_comp, [tracker_cls, params])
    except osa.framework.FrameworkException as e:
        raise cli.CliError(str(e))

def default_parameters_file():
    return 'detect.params'

def sample_linux_detect(tracker, params_file, name, load, overwrite):
    params = tracker.default_parameters.copy()
    if name:
        params["name"] = name
    if params_file is None and not load:
        params_file = default_parameters_file()
    if overwrite and not params_file:
        raise cli.CliError(
            'Cannot use -overwrite togheter with -load without param-file set')

    if params_file:
        save_params(tracker_cls, params, params_file, overwrite)
        return_msg = 'Saved parameters to %s' % params_file
    else:
        assert load
        return_msg = 'Loaded parameters'

    if load:
        set_params(tracker, params)

    return cli.command_return(value=params_file, message=return_msg)


def sample_linux_comp_detect(tracker_comp, *args):
    return sample_linux_detect(tracker_comp.tracker_obj, *args)

tracker_cls = 'sample_linux_tracker'
mapper_cls = 'sample_linux_mapper'
def add_sample_linux_tracker_commands():
    cli.new_info_command(tracker_cls, get_sample_linux_tracker_info)
    cli.new_status_command(tracker_cls, get_sample_linux_tracker_status)
    cli.new_info_command(mapper_cls, get_sample_linux_mapper_info)
    cli.new_status_command(mapper_cls, get_sample_linux_mapper_status)
    add_sample_linux_detect_command("sample_linux_tracker_comp",
                                    sample_linux_comp_detect)
    add_sample_linux_detect_command("sample_linux_tracker",
                                    sample_linux_detect)
add_sample_linux_tracker_commands()
