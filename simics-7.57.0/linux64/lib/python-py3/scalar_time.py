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


import operator
import cli, simics

SCALAR_TIME_INTERFACE = 'scalar_time'

# X axis constants.
class _Xaxis:
    @staticmethod
    def latest():
        return None
class NoXAxis(_Xaxis):
    name = None
class RealTime(_Xaxis):
    name = 'Real time (seconds)'
class SimTime(_Xaxis):
    name = 'Simulated time (seconds)'
    @staticmethod
    def latest():
        return simics.SIM_time(simics.VT_first_clock())

# Y axis constants.
class _Yaxis:
    minval = None
    maxval = None
def yaxis(unit, minval = None, maxval = None):
    minv = minval
    maxv = maxval
    class GenericYaxis(_Yaxis):
        name = unit
        minval = minv
        maxval = maxv
    return GenericYaxis
class Counts(_Yaxis):
    name = 'counts'
    minval = 0
class Bytes(_Yaxis):
    name = 'bytes'
    minval = 0
class Fraction(_Yaxis):
    name = 'Fraction'
    minval = 0
    maxval = 1
class NoYAxis(_Yaxis):
    name = None

# Data types.
class _Datatype:
    pass
class _Line(_Datatype):
    width = 2
    solid = False
class _Area(_Datatype):
    width = 1
    solid = True
class _BaseSample:
    @staticmethod
    def yaxis(s):
        return s
class Sample(_BaseSample, _Line):
    @staticmethod
    def lines(series):
        return series
class SampleArea(_BaseSample, _Area):
    @staticmethod
    def interpolate_series(s, times):
        i = iter(s)
        try:
            t0, y0 = next(i)
            t1, y1 = next(i)
        except StopIteration:
            # Not enough points in s to do any interpolation at all.
            for _ in range(len(times)):
                yield 0
            return
        for t in times:

            if t < t0:
                yield 0
                continue

            # Skip ahead to the correct interval.
            while t > t1:
                t0, y0 = t1, y1
                try:
                    t1, y1 = next(i)
                except StopIteration:
                    # We can't interpolate beyond the end of s.
                    assert False

            # At this point, t0 <= t <= t1.
            k = (y1 - y0)/(t1 - t0)
            yield k*(t - t0) + y0
    @staticmethod
    def series_toplist(series):
        def score(s):
            m = 1.0
            p = 0.0
            for i in range(min(len(s), 100)):
                p += m*(s[-i-1][1])
                m *= 0.95
            return p
        names = [name for score, name in
                 reversed(sorted((score(s), name) for name, s in series))]
        num = min(len(names), 5)
        for name in sorted(names[:num]):
            yield name, [name]
        if num < len(names):
            yield 'Other', names[num:]
    @classmethod
    def lines(cls, series):
        ends = [s[-1][0] for name, s in series if s]
        if not ends:
            # No data points in any of the series.
            return []
        end = min(ends)
        times = list(sorted(set(t for name, s in series
                                for t, y in s if t <= end)))
        acc = [0] * len(times)
        ls = []
        series_dict = dict(series)
        for newname, names in cls.series_toplist(series):
            for name in names:
                s = series_dict[name]
                acc = list(map(operator.add, acc, cls.interpolate_series(s, times)))
            ls.append((newname, zip(times, acc) + [(times[-1], 0),
                                                   (times[0], 0)]))
        ls.reverse()
        return ls
class Accumulator(_Line):
    @staticmethod
    def yaxis(s):
        return '%s/second' % s
    @staticmethod
    def one_line(series):
        i = iter(series)
        try:
            t0, y0 = next(i)
        except StopIteration:
            return
        for t, y in i:
            diff = t - t0
            if diff < 1e-10:
                # Merge too-short intervals.
                y += y0
            else:
                level = y0/(t - t0)
                yield (t0, level) # vertical line or first point
                yield (t, level) # horizontal line
            t0, y0 = t, y
    @classmethod
    def lines(cls, series):
        return [(name, list(cls.one_line(s))) for name, s in series]
class Blips(_Datatype):
    width = 1
    solid = False
    @staticmethod
    def yaxis(s):
        return None
    @staticmethod
    def lines(series):
        return [(name, [(t, 0) for t, foo in s]) for name, s in series]

class _ScalarTimePort:
    def __init__(self, cls, xaxis, yaxis, type, port):
        self.cls = cls     # string (class name)
        self.xaxis = xaxis
        assert issubclass(self.xaxis, _Xaxis)
        self.yaxis = yaxis
        assert issubclass(self.yaxis, _Yaxis)
        self.type = type
        assert issubclass(self.type, _Datatype)
        self.port = port   # string (port name)
    def iface(self, obj):
        return simics.SIM_get_port_interface(obj, SCALAR_TIME_INTERFACE,
                                             self.port)
    def portdesc(self):
        if self.port == None:
            return None
        return simics.CORE_get_port_description(self.cls, self.port) or self.port

class _ScalarTimePortStore:
    def __init__(self):
        self.__scalar_time_ports = set()
    def new_scalar_time_port(self, *args, **kwargs):
        stp = _ScalarTimePort(*args, **kwargs)
        ports = set(s.port for s in self.__scalar_time_ports
                    if s.cls == stp.cls)
        if stp.port in ports:
            raise cli.CliError(
                '%s tried to implement scalar time port "%s" twice'
                % (stp.cls, stp.port))
        ports.add(stp.port)
        if None in ports and len(ports) > 1:
            raise cli.CliError('%s tried to implement the scalar time interface'
                               ' both with and without a port name' % stp.cls)
        self.__scalar_time_ports.add(stp)
    def scalar_time_ports(self):
        ports = {}
        for stp in self.__scalar_time_ports:
            ports.setdefault(stp.cls, {})[stp.port] = stp
        for obj in simics.SIM_object_iterator(None):
            if obj.classname in ports:
                for port, stp in ports[obj.classname].items():
                    yield obj, stp

_stps = _ScalarTimePortStore()
new_scalar_time_port = _stps.new_scalar_time_port
scalar_time_ports = _stps.scalar_time_ports


# Utilities for Python devices implementing the scalar_time interface.

class _ConsumerSet:
    def __init__(self):
        self.consumers = set()
    def add_consumer(self):
        consumer = 0
        while consumer in self.consumers:
            consumer += 1
        self.consumers.add(consumer)
        return consumer
    def remove_consumer(self, consumer):
        self.consumers.remove(consumer)
    def __len__(self):
        return len(self.consumers)
    def __iter__(self):
        return iter(self.consumers)

class _Vect:
    def __init__(self, initial_consumers):
        self.samples = []
        self.consumed = {}
        for c in initial_consumers:
            self.add_consumer(c)
    def add_consumer(self, consumer):
        self.consumed[consumer] = 0
    def remove_consumer(self, consumer):
        del self.consumed[consumer]
        self.garbage_collect()
    def poll(self, consumer):
        old_ix = self.consumed[consumer]
        r = self.samples[old_ix:]
        self.consumed[consumer] = len(self.samples)
        self.garbage_collect()
        return r
    def garbage_collect(self):
        if self.consumed:
            i = min(self.consumed.values())
            if i > 0:
                for c in self.consumed.keys():
                    self.consumed[c] -= i
                self.samples = self.samples[i:]
        else:
            self.samples = []

class StatsPort:
    def __init__(self):
        self.consumers = _ConsumerSet()
        self.streams = {}
    def add_consumer(self):
        c = self.consumers.add_consumer()
        for sv in self.streams.values():
            sv.add_consumer(c)
        return c
    def remove_consumer(self, consumer):
        self.consumers.remove_consumer(consumer)
        for sv in self.streams.values():
            sv.remove_consumer(consumer)
    def poll(self, consumer):
        return [[key, val.poll(consumer)]
                for key, val in self.streams.items()]

class _SampleVect(_Vect):
    def new_sample(self, time, value):
        self.samples.append([time, value])

class SampleStatsPort(StatsPort):
    def new_sample(self, time, value, stream = ''):
        if self.consumers:
            sv = self.streams.get(stream, None)
            if not sv:
                sv = _SampleVect(self.consumers)
                self.streams[stream] = sv
            sv.new_sample(time, value)

class _BlipVect(_Vect):
    def new_blip(self, time):
        self.samples.append([time, 1])

class BlipStatsPort(StatsPort):
    def new_blip(self, time, stream = ''):
        if self.consumers:
            bv = self.streams.get(stream, None)
            if not bv:
                bv = _BlipVect(self.consumers)
                self.streams[stream] = bv
            bv.new_blip(time)
