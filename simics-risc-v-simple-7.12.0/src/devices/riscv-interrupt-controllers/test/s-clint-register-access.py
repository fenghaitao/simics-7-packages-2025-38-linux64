# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from riscv_intc_common import create_tb, Register_LE
import simics
import stest
from dev_util import MemoryError

tb = create_tb()

# CLINT register testing
for msip in tb.clint.msip:
    stest.expect_equal(msip.read(), 0)
    msip.write(-1)
    stest.expect_equal(msip.read(), 1)
    msip.write(0)
    stest.expect_equal(msip.read(), 0)

for mtimecmp in tb.clint.mtimecmp:
    stest.expect_equal(mtimecmp.read(), 0)
    mtimecmp.write(-1)
    stest.expect_equal(mtimecmp.read(), (1 << 64) - 1)

simics.SIM_run_command('%s.log-level 4' % tb.clint.obj.name)
stest.expect_equal(tb.clint.mtime.read(), 0)
tb.clint.mtime.write(-1)
stest.expect_equal(tb.clint.mtime.read(), (1 << 64) - 1)

bad_regs = [
    Register_LE(tb.clint.obj.bank.regs, tb.clint.msip[-1].ofs + 4, size=4),
    Register_LE(tb.clint.obj.bank.regs, tb.clint.mtimecmp[0].ofs - 8, size=8),
    Register_LE(tb.clint.obj.bank.regs, tb.clint.mtimecmp[-1].ofs + 8, size=8),
    Register_LE(tb.clint.obj.bank.regs, tb.clint.mtime.ofs - 8, size=8),
]
for reg in bad_regs:
    with stest.expect_log_mgr(log_type = 'spec-viol'):
        with stest.expect_exception_mgr(MemoryError):
            reg.read()

    with stest.expect_log_mgr(log_type = 'spec-viol'):
        with stest.expect_exception_mgr(MemoryError):
            reg.write(0)


cycle_stubs = {m: lambda *args: None
               for m in dir(simics.cycle_interface_t())
               if not m.startswith('__')}


class stallable:
    cls = simics.confclass('stallable')
    cls.attr.stall_cycles('i|n', default=None)

    cls.iface.cycle(**cycle_stubs)
    cls.iface.stall(get_stall_cycles=lambda *args: None,
                    get_total_stall_cycles=lambda *args: None)

    @cls.iface.stall.set_stall_cycles
    def set_stall_cycles(self, cycles):
        self.stall_cycles = cycles


ini = simics.SIM_create_object('stallable', 'ini')
t = simics.transaction_t(initiator=ini, size=8, read=True)

# Test no stalling configured
simics.SIM_issue_transaction(tb.clint.obj.bank.regs, t, tb.clint.mtime.ofs)
stest.expect_equal(ini.stall_cycles, None)

# Test stalling configured
tb.clint.obj.mtime_read_cycles = 42
simics.SIM_issue_transaction(tb.clint.obj.bank.regs, t, tb.clint.mtime.ofs)
stest.expect_equal(ini.stall_cycles, 42)

# Test unstallable initiator
t = simics.transaction_t(initiator=tb.clint.obj, size=8, read=True)
simics.SIM_issue_transaction(tb.clint.obj.bank.regs, t, tb.clint.mtime.ofs)
