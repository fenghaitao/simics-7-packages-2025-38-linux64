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

class_name = 'mem-traffic-meter'

def new_mem_traffic_meter_cmd(name):

    # Choose a name.
    real_name = cli_impl.new_object_name(name, 'mtm')
    if real_name == None:
        raise cli.CliError('An object called "%s" already exists.' % name)
    else:
        name = real_name

    simics.SIM_create_object(class_name, name,
                             [['queue', simics.VT_first_clock()]])
    if cli.interactive_command():
        print('New memory traffic meter %s created.' % name)

cli.new_command('new-' + class_name, new_mem_traffic_meter_cmd,
                [cli.arg(cli.str_t, 'name', '?', None)],
                type = ['Debugging'],
                short = 'create a memory traffic meter',
                doc = """
Create a memory traffic meter, optionally with a given <arg>name</arg>.""")

for d in ['source', 'target']:
    for u in ['byte', 'transaction']:
        scalar_time.new_scalar_time_port(
            class_name, scalar_time.SimTime,
            {'byte': scalar_time.Bytes, 'transaction': scalar_time.Counts}[u],
            scalar_time.Accumulator, '%s_%s' % (d, u))
