# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util
import simics
import stest
import random
random.seed("Rebel Heart")

dp = simics.SIM_create_object('pcie-downstream-port', 'dp', [])
cf8_cfc = simics.SIM_create_object('pci_cf8_cfc_handler', 'cf8_cfc', [["downstream_target",
                                                   dp.port.downstream]])
img = simics.SIM_create_object('image', 'img', [["size", 4]])
ram = simics.SIM_create_object('ram', 'ram', [["image", img]])

bus = random.randrange(1 << 8)
dev = random.randrange(1 << 5)
fun = random.randrange(1 << 3)
dword = random.randrange(1 << 6)
bdf = (bus << 8) | (dev << 3) | fun
addr = (bdf << 16) + (dword << 2)
val = int.to_bytes(random.randrange(1 << 32), 4, "little")

img.iface.image.set(0, val)
dp.cfg_space.map = [[addr, ram, 0, 0, 4]]

bf = dev_util.Bitfield_LE({'enable': 31,
                           'bus': (23, 16),
                           'dev': (15, 11),
                           'fun': (10, 8),
                           'dword': (7, 2)})
config_address = dev_util.Register_LE(cf8_cfc.bank.io_regs, 0xcf8, 4, bf)

# Add a breakpoint, it shouldn't hit on attribute access
bpid = simics.SIM_breakpoint(dp.cfg_space,
                             simics.Sim_Break_Physical,
                             simics.Sim_Access_Read | simics.Sim_Access_Write,
                             addr, 4, 0)


def callback(*args):
    stest.fail("read breakpoint shouldn't hit")


cbid = simics.SIM_hap_add_callback_index("Core_Breakpoint_Memop",
                                         callback, None, bpid)
simics.SIM_disable_breakpoint(bpid)

config_address.write(bus=bus, dev=dev, fun=fun, dword=dword)
for sz in (4, 2, 1):
    for offs in range(0, 4, sz):
        config_data = dev_util.Register_LE(cf8_cfc.bank.io_regs, 0xcfc + offs, sz)

        config_address.enable = 0
        exp_val = int.from_bytes(img.iface.image.get(offs, sz), "little")
        config_data.write(random.randrange(1 << (sz * 8)))
        got_val = int.from_bytes(img.iface.image.get(offs, sz), "little")
        stest.expect_equal(got_val, exp_val)  # not enabled

        config_address.enable = 1
        exp_val = random.randrange(1 << (sz * 8))
        config_data.write(exp_val)
        got_val = int.from_bytes(img.iface.image.get(offs, sz), "little")
        stest.expect_equal(got_val, exp_val)

        config_address.enable = 0
        stest.expect_equal(config_data.read(), 0)  # not enabled
        config_address.enable = 1
        stest.expect_equal(config_data.read(), exp_val)

        if sz == 4:
            # attribute getter, should use inquiry access
            simics.SIM_enable_breakpoint(bpid)
            stest.expect_equal(cf8_cfc.bank.io_regs.config_data, exp_val)
            exp_val = random.randrange(1 << (sz * 8))
            cf8_cfc.bank.io_regs.config_data = exp_val
            got_val = int.from_bytes(img.iface.image.get(offs, sz), "little")
            stest.expect_equal(got_val, exp_val)
            simics.SIM_disable_breakpoint(bpid)


# Test deferred transactions

def my_event(obj, func):
    func()

my_ev = simics.SIM_register_event("myev", None, Sim_EC_Notsaved,
                           my_event, None, None, None, None)

class ExecutionContextCallback:
    def __init__(self, func):
        self.f = func

    def __enter__(self):
        self.clock = SIM_create_object('clock', 'clock', freq_mhz=10)
        simics.SIM_event_post_cycle(self.clock, my_ev, self.clock, 0, self.callback)

    def __exit__(self, type, value, traceback):
        simics.SIM_delete_object(self.clock)
        assert self.f is None, "sanity check that the callback was executed"

    def callback(self):
        self.f()
        self.f = None

class tstub:
    cls = simics.confclass('tstub')
    cls.iface.transaction()
    cls.iface.pcie_port_control()

    cls.attr.deferred('i|n', default=None, optional=True)
    cls.attr.complete('i', pseudo=True, kind=simics.Sim_Attr_Write_Only)

    @cls.attr.complete.setter
    def complete_setter(self, val):
        self.deferred.value_le = val
        simics.SIM_complete_transaction(
            self.deferred, simics.Sim_PE_No_Exception)
        self.deferred = None

    @cls.iface.transaction.issue
    def issue(self, t, offset):
        stest.expect_true(self.deferred is None)

        self.deferred = simics.SIM_defer_transaction(self.obj, t)
        stest.expect_true(self.deferred is not None)
        return simics.Sim_PE_Deferred
    @cls.iface.pcie_port_control.set_secondary_bus_number
    def set_secondary_bus_number(val):
        print("Set secondary bus number:", val)
    @cls.iface.pcie_port_control.hot_reset
    def hot_reset():
        print("Hot reset")


tstub = simics.SIM_create_object('tstub', 'tstub')
cf8_cfc.downstream_target = tstub
config_data = dev_util.Register_LE(cf8_cfc.bank.io_regs, 0xcfc, 4)

def test_deferred_read():
    val = config_data.read()
    stest.expect_equal(val, 0x12345678)

with ExecutionContextCallback(test_deferred_read):
    simics.SIM_continue(1)
    tstub.complete = 0x12345678
    simics.SIM_continue(1)
