# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import cli, cli_impl, scalar_time, simics

class_name = 'hap-meter'

class HapMeterPolicy:
    def __init__(self, obj):
        self.obj = obj
        self.active = False
    def has_consumers(self, has_consumers):
        if has_consumers and not self.active:
            self.activate()
        elif not has_consumers and self.active:
            self.deactivate()
        self.active = has_consumers
    def activate(self):
        pass
    def deactivate(self):
        pass
    def description(self):
        return ('Not activated', [])
    def status(self):
        title, params = self.description()
        return [(title, params + [
            ('Currently serving data', self.active)])]

def new_hap_meter_cmd(name):
    # Choose a name.
    real_name = cli_impl.new_object_name(name, 'hap_meter')
    if real_name == None:
        raise cli.CliError('An object called "%s" already exists.' % name)
    else:
        name = real_name
    simics.SIM_create_object(class_name, name,
                             [['queue', simics.VT_first_clock()]])
    if cli.interactive_command():
        print('New hap meter %s created.' % name)
cli.new_command('new-' + class_name, new_hap_meter_cmd,
                [cli.arg(cli.str_t, 'name', '?', None)],
                type = ['Debugging'],
                short = 'create a new hap meter',
                see_also = ['<%s>.%s' % (class_name, cmd) for cmd in
                            ['listen-for-exceptions', 'listen-for-hap']],
                doc = """
Create a new hap meter, optionally with a given <arg>name</arg>.

The new hap meter can then be instructed to collect statistics on the
occurrence of various haps, and the result visualized in the GUI's Statistics
Plot window.""")

scalar_time.new_scalar_time_port(
    class_name, scalar_time.SimTime, scalar_time.NoYAxis,
    scalar_time.Blips, port = None)
