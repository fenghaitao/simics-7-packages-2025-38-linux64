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

import collections
from simics import *


DELTA_MODE = "delta"
SESSION_MODE = "session"
CURRENT_MODE = "current"


class IllegalProbeValue(Exception):
    pass

class IllegalProbeMode(Exception):
    pass

class ProbeAlreadySampled(Exception):
    pass


class SampledProbes:
    '''Provides the mechanisms to deal with a collection
    of probes sampled by a sampler'''

    __slots__ = ("_sprobes")

    def __init__(self):
        self._sprobes = collections.OrderedDict()

    def all(self):
        return self._sprobes.values()

    def create(self, probe_proxy, mode, hidden, no_sampling):
        unique_id = self.generate_unique_id(probe_proxy, mode)

        # Check not already sampled
        if self.is_sampled(unique_id):
            raise ProbeAlreadySampled(f"Already added: {probe_proxy.cli_id}")

        def check_delta_mode_supported():
            if not probe_proxy.type_class.delta_support():
                raise IllegalProbeMode(
                    f"cannot show '{mode}' values, only '{CURRENT_MODE}' supported")

        if mode == DELTA_MODE or mode == SESSION_MODE:
            check_delta_mode_supported()

        if mode == DELTA_MODE:
            return ProbeInDeltaMode(probe_proxy, unique_id, hidden, no_sampling)
        elif mode == SESSION_MODE:
            return ProbeInSessionMode(probe_proxy, unique_id, hidden, no_sampling)
        elif mode == CURRENT_MODE:
            return ProbeInCurrentMode(probe_proxy, unique_id, hidden, no_sampling)
        else:
            assert 0

    def generate_unique_id(self, probe_proxy, mode):
        type = ("-" + mode) if mode != DELTA_MODE else ""
        unique_id =  probe_proxy.cli_id + type
        return unique_id

    def add(self, sp):
        self._sprobes[sp.unique_id] = sp

    def remove(self, sp):
        if sp.unique_id in self._sprobes:
            self._sprobes[sp.unique_id].unsubscribe()
            del self._sprobes[sp.unique_id]
            return True
        return False

    def is_sampled(self, unique_id):
        return unique_id in self._sprobes

    def none_sampled(self):
        return not self._sprobes

    def terminate(self):
        for sp in self._sprobes.values():
            sp.unsubscribe()

    def reset_session(self):
        for sp in self._sprobes.values():
            sp.reset_session()


class SampledProbe:
    '''Provides access to a probe's value and its history, depending on
    the sampling mode and some other sampling properties'''

    __slots__ = ("probe_proxy", "mode", "unique_id", "hidden",
                 "no_sampling", "_raw_history")

    def __init__(self, probe_proxy, mode, unique_id, hidden, no_sampling):
        # probe instance from core/src/core/common/probes
        self.probe_proxy = probe_proxy
        self.mode = mode
        self.unique_id = unique_id
        self.hidden = hidden
        self.no_sampling = no_sampling
        self._raw_history = [] # The collected samples
        self._setup()

    def _setup(self):
        self.subscribe()

        init_value = self.probe_proxy.value()
        if not self.valid_value(init_value):
            self.unsubscribe()
            raise IllegalProbeValue("invalid value in probe")

    def subscribe(self):
        self.probe_proxy.subscribe()

    def unsubscribe(self):
        self.probe_proxy.unsubscribe()

    def sample_value(self):
        '''Return the probe value as read by a sampler'''
        assert 0

    def actual_value(self):
        '''Return the instantaneous probe value'''
        assert 0

    def valid_value(self, value):
        '''Check if the probe-type has a valid value'''
        return self.probe_proxy.type_class.valid_value(value)

    def get_unique_id(self):
        return self.unique_id

    def unique_id_matches_name(self, name):
        if self.unique_id == name:
            return True

        if ":" in self.unique_id:
            probe_name = self.unique_id.split(":") [1] # Skip object
            return probe_name == name

        return False

    def add_to_history(self, raw_value):
        self._raw_history.append(raw_value)

    def get_history_index(self, idx):
        return self._raw_history[idx]

    def get_history(self):
        return self._raw_history

    def clear_history(self):
        self._raw_history = []

    def add_missing_samples_to_history(self, num):
        nv = self.probe_proxy.type_class.neutral_value()
        self._raw_history = [nv] * num

    def reset_session(self):
        pass                    # overridden by DeltaProbes

    def __repr__(self):
        return self.unique_id


class DeltaProbe(SampledProbe):
    '''A sampled probe that supports delta calculation, ie the calculation of value difference
    between samples'''

    __slots__ = ("_start_value")

    def __init__(self, probe_proxy, mode, unique_id, hidden, no_sampling):
        super().__init__(probe_proxy, mode, unique_id, hidden, no_sampling)
        self._start_value = self.probe_proxy.value()

    def _session_value(self):
        '''Calculate the delta-value from first sample'''
        return self.probe_proxy.type_class.diff_values(
            self.probe_proxy.value(), self._start_value)

    def reset_session(self):
        self._start_value = self.probe_proxy.value()

class ProbeInDeltaMode(DeltaProbe):
    '''A delta probe sampled in delta mode'''

    __slots__ = ("_new_value", "_old_value")

    def __init__(self, probe_proxy, unique_id, hidden, no_sampling):
        super().__init__(probe_proxy, DELTA_MODE, unique_id, hidden, no_sampling)
        self._new_value = self._start_value
        self._old_value = self._start_value

    def prepare_sample(self):
        '''Should be called ONCE each sample to correctly handle the
        delta values between samples'''
        self._old_value = self._new_value
        self._new_value = self.probe_proxy.value()

    def sample_value(self):
        '''Calculate the delta-value from last sample'''
        return self.probe_proxy.type_class.diff_values(
            self._new_value, self._old_value)

    def actual_value(self):
        return self._session_value()

    def reset_session(self):
        super().reset_session()
        self._new_value = self._start_value
        self._old_value = self._start_value

class ProbeInSessionMode(DeltaProbe):
    '''A delta probe sampled in session mode'''

    __slots__ = ()

    def __init__(self, probe_proxy, unique_id, hidden, no_sampling):
        super().__init__(probe_proxy, SESSION_MODE, unique_id, hidden, no_sampling)

    def sample_value(self):
        return self._session_value()

    def actual_value(self):
        return self._session_value()


class ProbeInCurrentMode(SampledProbe):
    '''A sampled probe sampled in current mode'''

    __slots__ = ("_sample_value_fn")

    def __init__(self, probe_proxy, unique_id, hidden, no_sampling):
        super().__init__(probe_proxy, CURRENT_MODE, unique_id, hidden, no_sampling)
        self.install_sample_value_function()

    def install_sample_value_function(self):
        type_class = self.probe_proxy.type_class
        if type_class.sorting_support():
            self._sample_value_fn = lambda: type_class.sorted(self.probe_proxy.value())
        else:
            self._sample_value_fn = self.probe_proxy.value

    def sample_value(self):
        return self._sample_value_fn()

    def actual_value(self):
        return self.sample_value()
