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

import cli, scalar_time
import simics

class RealtimeCallback:
    def __init__(self, period, callback):
        self.period = period
        self.user_callback = callback
        self.callback_id = None
    def start(self):
        if self.callback_id != None:
            return
        self.callback() # will start periodic callback
    def stop(self):
        if self.callback_id == None:
            return
        simics.SIM_cancel_realtime_event(self.callback_id)
        self.callback_id = None
    def callback(self, *args):
        self.user_callback()
        self.callback_id = simics.SIM_realtime_event(
            1000*self.period, self.callback, None, False,
            'periodic realtime callback')

class SimtimeCallback:
    def __init__(self, period, callback, obj):
        self.period = period
        self.user_callback = callback
        self.obj = obj
        self.callback_active = False
        self.event_class = simics.SIM_register_event(
            'periodic simtime callback', None, simics.Sim_EC_Notsaved,
            self.callback, None, None, None, None)
    def start(self):
        if self.callback_active:
            return
        self.callback_active = True
        self.callback() # will start periodic callback
    def stop(self):
        simics.SIM_event_cancel_time(
            self.obj.queue, self.event_class, self.obj, None, None)
        self.callback_active = False
    def callback(self, *args):
        self.user_callback()
        simics.SIM_event_post_time(
            self.obj.queue, self.event_class, self.obj, self.period, None)

class DualCallback:
    def __init__(self, real_period, sim_period, callback, obj):
        if real_period:
            self.real = RealtimeCallback(real_period, callback)
        else:
            self.real = None
        if sim_period:
            self.sim = SimtimeCallback(sim_period, callback, obj)
        else:
            self.sim = None
    def start(self):
        if self.real != None:
            self.real.start()
        if self.sim != None:
            self.sim.start()
    def stop(self):
        if self.real != None:
            self.real.stop()
        if self.sim != None:
            self.sim.stop()

class AttrMeter:
    class_name = 'attr-meter'
    @classmethod
    def declare_period_attr(cls, name, desc):
        def getter(arg, obj, idx):
            return float(getattr(obj.object_data, name))
        def setter(arg, obj, val, idx):
            am = obj.object_data
            if val != None and val <= 0:
                return simics.Sim_Set_Illegal_Value
            setattr(am, name, val)
            am.callback.stop()
            am.callback = DualCallback(am.realtime_period, am.simtime_period,
                                       am.periodic_sample, am.obj)
            am.callback_on_off()
            return simics.Sim_Set_Ok
        simics.SIM_register_typed_attribute(
            cls.class_name, name, getter, None, setter, None,
            simics.Sim_Attr_Required, 'f|n', None,
            'Sample period (%s), in seconds, or nil to disable sampling' % desc)
    @classmethod
    def declare_info_status(cls):
        def get_info(obj):
            return []
        def get_status(obj):
            return obj.object_data.status()
        cli.new_info_command(cls.class_name, get_info)
        cli.new_status_command(cls.class_name, get_status)
    @classmethod
    def declare_class(cls):
        def init_object(obj, arg):
            return cls(obj)
        cls.class_data = simics.class_data_t()
        cls.class_data.init_object = init_object
        cls.class_data.kind = simics.Sim_Class_Kind_Pseudo
        cls.class_data.description = 'Attribute meter'
        cls.class_data.class_desc = "attribute meter"
        simics.SIM_register_class(cls.class_name, cls.class_data)
        cls.declare_stats_port('value', 'value', scalar_time.Sample,
                               'Attribute value')
        cls.declare_stats_port('derivative', 'value', scalar_time.Accumulator,
                               'Attribute delta')
        cls.declare_period_attr('realtime_period', 'real time')
        cls.declare_period_attr('simtime_period', 'simulated time')
        cls.declare_info_status()
    @classmethod
    def declare_stats_port(cls, port, yaxis, type, desc):
        ifc = simics.scalar_time_interface_t()
        def add_consumer(obj):
            c = obj.object_data.ports[port].add_consumer()
            obj.object_data.callback_on_off()
            return c
        ifc.add_consumer = add_consumer
        def remove_consumer(obj, consumer):
            obj.object_data.ports[port].remove_consumer(consumer)
            obj.object_data.callback_on_off()
        ifc.remove_consumer = remove_consumer
        def poll(obj, consumer):
            return obj.object_data.ports[port].poll(consumer)
        ifc.poll = poll
        simics.SIM_register_port_interface(cls.class_name, 'scalar_time', ifc,
                                           port, desc)
        scalar_time.new_scalar_time_port(
            cls.class_name, scalar_time.SimTime, scalar_time.yaxis(yaxis),
            type, port)
    def __init__(self, obj):
        self.obj = obj
        self.ports = { 'value': scalar_time.SampleStatsPort(),
                       'derivative': scalar_time.SampleStatsPort() }
        self.realtime_period = None
        self.simtime_period = None
        self.callback = DualCallback(self.realtime_period, self.simtime_period,
                                     self.periodic_sample, self.obj)
        self.last_val = None
    def has_consumers(self):
        return any(p.consumers for p in self.ports.values())
    def callback_on_off(self):
        if self.has_consumers():
            self.callback.start()
        else:
            self.callback.stop()
    def periodic_sample(self):
        if simics.SIM_simics_is_running():
            time = simics.SIM_time(self.obj.queue)
            val = self.getattr()
            self.ports['value'].new_sample(time, val)
            if self.last_val != None:
                self.ports['derivative'].new_sample(time, val - self.last_val)
            self.last_val = val
    def status(self):
        def period(x):
            if x == None:
                return 'off'
            else:
                return '%.3f s' % x
        return [(None,
                 [('Watching attribute', self.desc),
                  ('Realtime polling', period(self.realtime_period)),
                  ('Simulated time polling', period(self.simtime_period)),
                  ('Currently serving data', self.has_consumers())])]
