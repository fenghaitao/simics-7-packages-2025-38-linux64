# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from simics import *
from cli import (
    CliError, new_command, get_completions, new_status_command,
    new_info_command,
)
import cli
import systempanel

def state_manager_get_info(obj):
    polled = set(obj.polled_panel_objects)
    active_panel_objects = [o for o in obj.panel_objects
                            if not o in polled]
    objs = [(name, ls) for (name, ls) in
            [('Objects updated actively', active_panel_objects),
             ('Objects using polling', obj.polled_panel_objects)]
            if ls]

    return [('Connections', [('Frontend', obj.front_end),
                             ('Recorder', obj.recorder),
                             ('Use recorder', obj.use_recorder)]),
            ('Panel objects', objs)]

def sp_number_get_info(obj):
    return [('Connections', [('target', obj.target),
                             ('authority', obj.authority)])]

def sp_bool_get_info(obj):
    return [(None, [('target', obj.target),
                    ('authority', obj.authority)])]

cli.new_info_command('system_panel_state_manager', state_manager_get_info)
cli.new_info_command('system_panel_number', sp_number_get_info)
cli.new_info_command('system_panel_bool', sp_bool_get_info)

def state_manager_get_status(obj):
    return [(None,
             [('State changes notification sent', obj.notification_sent)])]

def sp_number_get_status(obj):
    return [(None,
             [('State', obj.number_state)])]

def sp_signal_get_status(obj):
    return [(None,
             [('State', "high" if obj.bool_state else "low")])]

cli.new_status_command('system_panel_state_manager', state_manager_get_status)
cli.new_status_command('system_panel_number', sp_number_get_status)
cli.new_status_command('system_panel_bool', sp_signal_get_status)

def connect_panel_to_frontend_cmd(panel, frontend):
    if not isinstance(panel.object_data, systempanel.SystemPanel):
        raise CliError("Argument error: %s is not an instance of "
                       "SystemPanel" % panel.name)

    existing = panel.panel_state_manager.front_end
    if existing:
        panels = list(existing.system_panels)
        panels.remove(panel)
        existing.system_panels = panels
        existing.iface.system_panel_frontend.layout_changed()
        existing.iface.system_panel_frontend.state_changed()

    frontend.system_panels = list(frontend.system_panels) + [panel]
    panel.panel_state_manager.front_end = frontend

    # Notify frontend the layout and state changed
    frontend.iface.system_panel_frontend.layout_changed()
    frontend.iface.system_panel_frontend.state_changed()

cli.new_command('connect-panel-to-frontend', connect_panel_to_frontend_cmd,
                [cli.arg(cli.obj_t("panel", 'system_panel_layout'), 'panel'),
                 cli.arg(cli.obj_t("frontend", 'system_panel_frontend'),
                         'frontend')],
                short = "connect panel to frontend",
                doc = """
Connects the <arg>panel</arg> object to a <arg>frontend</arg>
object. The panel, which belongs to the modeled system, displays
visible parts of the system, for example LED's. The frontend object
belongs to the simulator and controls how to present the panel. Use
tab completion to find available panels and frontend objects.""")
