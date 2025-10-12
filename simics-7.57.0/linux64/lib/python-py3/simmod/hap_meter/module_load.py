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

import cli, simics

from .simics_start import HapMeterPolicy, class_name

def swap_hap_meter_policy(obj, new_policy):
    old_policy = obj.object_data
    obj.object_data = new_policy
    if old_policy.active:
        old_policy.deactivate()
        new_policy.active = True
        new_policy.activate()

def exception_objects():
    return list(simics.SIM_object_iterator_for_interface(['exception']))

class ExceptionHapMeter(HapMeterPolicy):
    hap = 'Core_Exception'
    def __init__(self, obj, cpu, exc_name):
        HapMeterPolicy.__init__(self, obj)
        self.cpu = cpu
        self.exc_name = exc_name
        if exc_name == None:
            self.exc_nr = None
        else:
            if self.cpu == None:
                cpus = exception_objects()
            else:
                cpus = [self.cpu]
            self.exc_nr = set(exc_nr for cpu in cpus
                              for exc_nr
                              in cpu.iface.exception.all_exceptions()
                              if (cpu.iface.exception.get_name(exc_nr)
                                  == exc_name))
            if not self.exc_nr:
                raise cli.CliError('%s: bad exception name' % self.exc_name)
    def activate(self):
        if self.cpu == None and self.exc_nr == None:
            self.callback_id = [simics.SIM_hap_add_callback(
                self.hap, self.exception_callback, None)]
        elif self.cpu != None and self.exc_nr == None:
            self.callback_id = [simics.SIM_hap_add_callback_obj(
                self.hap, self.cpu, 0, self.exception_callback, None)]
        elif self.cpu == None and self.exc_nr != None:
            self.callback_id = [simics.SIM_hap_add_callback_index(
                self.hap, self.exception_callback, None, exc_nr)
                                for exc_nr in self.exc_nr]
        else:
            self.callback_id = [simics.SIM_hap_add_callback_obj_index(
                self.hap, self.cpu, 0, self.exception_callback,
                None, exc_nr) for exc_nr in self.exc_nr]
    def deactivate(self):
        for cid in self.callback_id:
            simics.SIM_hap_delete_callback_id(self.hap, cid)
    def exception_callback(self, data, obj, exc_nr):
        exc_name = obj.iface.exception.get_name(exc_nr)
        if self.exc_name in [exc_name, None]:
            self.obj.blip = obj.name + ': ' + exc_name
    def description(self):
        if self.cpu == None:
            cpu = 'all'
        else:
            cpu = self.cpu.name
        return ('Listening for exceptions',
                [('Processor', cpu),
                 ('Exception type', self.exc_name or 'all')])

def listen_for_exceptions_cmd(obj, cpu, exc_name):
    swap_hap_meter_policy(obj, ExceptionHapMeter(obj, cpu, exc_name))
def exception_expander(s):
    return cli.get_completions(
        s, set(cpu.iface.exception.get_name(exc_nr)
               for cpu in exception_objects()
               for exc_nr in cpu.iface.exception.all_exceptions()))
cli.new_command('listen-for-exceptions', listen_for_exceptions_cmd,
                [cli.arg(cli.obj_t('processor', 'exception'),
                         'processor', '?', None),
                 cli.arg(cli.str_t, 'exception', '?', None,
                         expander = exception_expander)],
                type = ['Debugging'], cls = class_name,
                short = 'listen for exception haps',
                see_also = ['new-hap-meter'],
                doc = """
Instruct the hap meter to listen for exceptions on the given
<arg>processor</arg> (or all processors, if none is given). You may restrict
the listening to a specific type of <arg>exception</arg>; if you do not, all
exceptions will be collected.""")

class SimpleHapMeter(HapMeterPolicy):
    def __init__(self, obj, hap, tgt_obj):
        HapMeterPolicy.__init__(self, obj)
        self.hap = hap
        self.tgt_obj = tgt_obj
    def activate(self):
        if self.tgt_obj == None:
            self.callback_id = [simics.SIM_hap_add_callback(
                self.hap, self.hap_callback, None)]
        else:
            self.callback_id = [simics.SIM_hap_add_callback_obj(
                self.hap, self.tgt_obj, 0, self.hap_callback, None)]
    def deactivate(self):
        for cid in self.callback_id:
            simics.SIM_hap_delete_callback_id(self.hap, cid)
    def hap_callback(self, data, obj, *args):
        if self.tgt_obj == None:
            self.obj.blip = self.hap
        else:
            self.obj.blip = obj.name + ': ' + self.hap
    def description(self):
        if self.tgt_obj == None:
            obj = 'all'
        else:
            obj = self.tgt_obj.name
        return ('Listening for a hap',
                [('Hap', self.hap),
                 ('Object', obj)])

def listen_for_hap_cmd(obj, hap, tgt_obj):
    swap_hap_meter_policy(obj, SimpleHapMeter(obj, hap, tgt_obj))
def hap_expander(s):
    return cli.get_completions(s, simics.SIM_get_all_hap_types())
cli.new_command('listen-for-hap', listen_for_hap_cmd,
                [cli.arg(cli.str_t, 'hap', expander = hap_expander),
                 cli.arg(cli.obj_t('object'), 'object', '?', None)],
                type = ['Debugging'], cls = class_name,
                short = 'listen for a specified hap',
                see_also = ['new-hap-meter'],
                doc = """
Instruct the hap meter to listen for a certain <arg>hap</arg>. You may
restrict the listening to a specific <arg>object</arg>; if you do not, haps
triggered by all objects will be collected.""")

def set_init(arg, obj, val, idx):
    obj.object_data = HapMeterPolicy(obj)
    return simics.Sim_Set_Ok
simics.SIM_register_typed_attribute(
    class_name, 'init',
    None, None, set_init, None, simics.Sim_Attr_Pseudo, 'n', None,
    'Initialize object')

def set_has_consumers(arg, obj, val, idx):
    obj.object_data.has_consumers(val)
    return simics.Sim_Set_Ok
simics.SIM_register_typed_attribute(
    class_name, 'has_consumers',
    None, None, set_has_consumers, None, simics.Sim_Attr_Pseudo, 'b', None,
    'Does the meter have any consumers?')

def info_status():
    def get_info(obj):
        return []
    def get_status(obj):
        return obj.object_data.status()
    cli.new_info_command(class_name, get_info)
    cli.new_status_command(class_name, get_status)
info_status()
