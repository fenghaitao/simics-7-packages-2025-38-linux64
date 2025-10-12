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

scalar_time.enable = True
class_name = 'attr-meter'

def acceptable_attr(type):
    return isinstance(type, str) and set(type.split('|')) <= set('if')

class SpecError(Exception):
    pass
def parse_spec(attribute):
    try:
        (obj, attr) = attribute.rsplit('.', 1)
    except ValueError:
        raise SpecError('%s: no such attribute.' % attribute)
    try:
        obj = simics.SIM_get_object(obj)
    except simics.SimExc_General:
        raise SpecError('%s: no such object.' % obj)
    for name, _, _, type in obj.attributes:
        if name == attr:
            if acceptable_attr(type):
                return obj, attr
            else:
                raise SpecError('%s: attribute has wrong type' % attribute)
    raise SpecError('%s: object %s has no such attribute' % (attr, obj.name))

def new_attr_meter_cmd(name, attribute, real_period, sim_period):
    try:
        tgt_obj, attr = parse_spec(attribute)
    except SpecError as e:
        raise cli.CliError(str(e))
    def get_attribute():
        return float(getattr(tgt_obj, attr))
    real_name = cli_impl.new_object_name(name, 'attr_meter')
    if real_name == None:
        raise cli.CliError('An object called "%s" already exists.' % name)
    else:
        name = real_name
    obj = simics.SIM_create_object(class_name, name,
                                   [['queue', simics.VT_first_clock()],
                                    ['realtime_period', real_period],
                                    ['simtime_period', sim_period]])
    obj.object_data.getattr = get_attribute
    obj.object_data.desc = attribute
    return cli.command_return('New attribute meter %s created.' % name, obj)



def attr_expander(s):
    exp = []
    if '.' in s:
        try:
            obj, attr = s.split('.')
        except ValueError:
            return []
        try:
            obj = simics.SIM_get_object(obj)
        except simics.SimExc_General:
            return []
        for name, _, _, type in obj.attributes:
            if name.startswith(attr) and acceptable_attr(type):
                exp.append(obj.name + '.' + name)
    else:
        for obj in (obj.name for obj in simics.SIM_object_iterator(None)):
            if obj.startswith(s):
                if obj == s:
                    exp.append(obj + '.')
                else:
                    exp.append(obj)
    return exp

cli.new_command('new-' + class_name, new_attr_meter_cmd,
                [cli.arg(cli.str_t, 'name', '?', None),
                 cli.arg(cli.str_t, 'attribute', expander = attr_expander),
                 cli.arg(cli.float_t, 'realtime-period', '?', 0.25),
                 cli.arg(cli.float_t, 'simtime-period', '?', 0.1)],
                type = ['Debugging'],
                short = 'create an attribute meter',
                doc = """
Create an attribute meter that makes it possible to visualize attributes in
the GUI's Statistics Plot window.

Optionally it may be given a <arg>name</arg>. The <arg>attribute</arg>
argument must be specified as <i>objectname</i>.<i>attributename</i>. The
attribute must be numerical (i.e., have type <tt>i</tt> or <tt>f</tt>).

<arg>realtime-period</arg> and <arg>simtime-period</arg> determines how often
to poll the attribute, in seconds of real and simulated time, respectively.""")
