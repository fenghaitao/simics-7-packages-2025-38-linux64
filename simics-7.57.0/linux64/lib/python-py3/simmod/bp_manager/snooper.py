# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import unittest

import simics
import conf
import cli_impl
import snoop
from .bp_type import bp_cb, bp_args, to_attr_value

class BP(snoop.Snooper):
    def __init__(self, provider, *args, **kwargs):
        if not simics.SIM_c_get_interface(
                provider, 'breakpoint_type_provider'):
            raise snoop.InvalidObjError(
                f"object {provider.name} does not implement the"
                "  breakpoint_type_provider interface")
        self.provider = provider
        # Extract CLI-style arglist from BP type
        (have_obj, cli_args) = bp_args[provider]
        # Utilize the CLI-to-Python argument mapping logic used by
        # .cli_cmds to map cli_cmds-style *args/**kwargs to arglist of
        # CLI implementation function
        result = []
        (fun, *_) = cli_impl.wrap_cmd_fun(
            lambda *args: result.append(args), cli_args, None, None)
        fun(*args, **kwargs)
        [args_from_cli] = result
        self.obj = args_from_cli[0] if have_obj else None
        # Convert CLI arglist to BP interface format. Add hardcoded
        # value for the extra -once flag
        self.args = to_attr_value(args_from_cli) + [False]

    def add_callback(self, cb, exc_bridge):
        bp_id = self.provider.iface.breakpoint_type_provider.add_bp(
            simics.Breakpoint_Type_Default, self.args)
        if bp_id == 0:
            raise snoop.Error(
                f'Failed to listen to {self.provider.name}'
                f' with args {self.args}')
        def wrapper(obj, desc):
            break_data = self.provider.iface.breakpoint_type_provider.break_data
            cb(break_data(bp_id) if break_data else None)
        bp_cb[(self.provider, bp_id)] = [
            (simics.Breakpoint_Type_Default, wrapper, [], None)]
        def remove_breakpoint(_=None):
            self.provider.iface.breakpoint_type_provider.remove_bp(bp_id)
        if self.obj:
            return snoop.object_handle(self.obj, remove_breakpoint)
        else:
            class Handle(snoop.Handle):
                def __init__(self):
                    self.cancelled = False
                def cancel(self):
                    if not self.cancelled:
                        self.cancelled = True
                        remove_breakpoint()
            return Handle()

    def exec_context(self):
        return snoop.GlobalContext()


class TestBP(unittest.TestCase):
    def test_bp(self):
        ls = []
        def cb(arg):
            ls.append(arg)
        handle = snoop.add_callback_simple(
            BP(conf.bp.log, object=conf.sim, type='info'), cb)
        simics.SIM_log_info(1, conf.sim, 0, 'hello world')
        self.assertEqual(ls, [[
            None, None, None, 1, 0, 1, conf.sim, 'hello world']])
        del ls[:]
        handle.cancel()
        simics.SIM_log_info(1, conf.sim, 0, 'hello world')
        self.assertEqual(ls, [])
        handle = snoop.add_callback_simple(
            BP(conf.bp.notifier, name='global-objects-finalized', _global=True),
            cb)
        simics.SIM_delete_object(simics.SIM_create_object('memory-space', None))
        self.assertEqual(ls, [None])
        del ls[:]
        handle.cancel()
        simics.SIM_delete_object(simics.SIM_create_object('memory-space', None))
        self.assertEqual(ls, [])

        # Clock breakpoints are tricky because of the
        clock = simics.SIM_create_object('clock', None, freq_mhz=1)
        try:
            handle = snoop.add_callback_simple(
                BP(conf.bp.time, object=clock, seconds=0.001), cb)
            simics.SIM_continue(3000)
            self.assertEqual(ls, [None])
            handle.cancel()
        finally:
            simics.SIM_delete_object(clock)
