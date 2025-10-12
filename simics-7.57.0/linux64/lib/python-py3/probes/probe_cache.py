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


from simics import *
import conf

import functools

# Decorator for cached access of a probe. The method which used this
# decorator, should only have a 'self' as an argument.
#
# With caching enabled, probes can return the previous value back,
# avoiding expensive calculation, if they are read multiple times
# (either directly or indirectly from other probes). It can also be
# used to avoid probe values to return a slightly different value the
# next time in the same sample, such as wallclock time.
#
# The samplers are responsible for enabling caching when taking
# a sample. Using the probe_sampler_cache->enable() method.
# This increments a generation id specific for this cached session.
#
# As long as the object has a cached value from the same generation
# id, this cached value can be returned.
#
# When sampling is finished the probe_sampler_cache->disable()
# will be called, causing the "not-cached" generation id of zero
# to be returned.
#
# If several probes should share the same cache, the method needs
# to be put on a class with a singleton object, which is used to
# share the probe value.
class cached_probe_read:
    __slots__ = ('read_func', 'cache', 'iface')
    def __init__(self, read_func):
        self.read_func = read_func
        self.cache = {}         # {obj: (gen, value)}
        # TODO: cache the interface here when the python code
        # is loaded when enable-probes is executed.
        self.iface = None

    def generation_id(self):
        if not self.iface:
            self.iface = conf.probes.iface.probe_sampler_cache
        return self.iface.get_generation()

    def __call__(self, obj):
        gen_ctr = self.generation_id()
        if gen_ctr and obj in self.cache:
            (cached_gen, cached_value) = self.cache[obj]
            if gen_ctr == cached_gen:
                return cached_value

        value = self.read_func(obj)
        if gen_ctr:
            self.cache[obj] = (gen_ctr, value)
        return value

    # Convert the instance to a method, which runs __call__
    # and encapsulates the owning object as first argument.
    def __get__(self, obj, cls):
        return functools.partial(self.__call__, obj)
