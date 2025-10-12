# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from contextlib import nullcontext

import itertools
import random
import simics
import stest
from pcie_downstream_port_common import check, legacy_rc, new_addr

random.seed("Everybody Knows")

(rc, pci_devices) = legacy_rc("rc")

# Sanity check on pci_devices attribute
exp_devices = [e + [1] for e in pci_devices]
stest.expect_equal(rc.dp.pci_devices, exp_devices)

# Check that conf_space looks as expected
stest.expect_equal(rc.dp.iface.pci_bus.configuration_space(), rc.dp.conf_space)
stest.expect_equal(rc.dp.conf_space.map, [])
stest.expect_equal(rc.dp.conf_space.default_target,
                   [rc.dp.impl.conf_to_cfg, 0, 0, rc.dp.cfg_space, 0, 0])

# Check that memory_space interface works as expected
mem_ifc = rc.dp.conf_space.iface.memory_space
for i, (df, obj) in enumerate(rc.dp.functions):
    d = df >> 3
    f = df & 0x7
    if hasattr(obj.iface, 'pcie_device'):
        continue
    addr = (d << 3 | f) << 12
    val = random.randrange(256)
    mem_ifc.write(None, addr, (val,), False)
    stest.expect_equal(obj.tx_addr, 0)
    stest.expect_equal(obj.tx_val, val)
    stest.expect_equal(obj.map_fun, 255)
    stest.expect_equal(mem_ifc.read(None, addr, 1, False), (val,))

# Check that map_demap interface works as expected
map_ifc = rc.dp.conf_space.iface.map_demap
bdf = random.randrange(256) << 8
vf = simics.SIM_create_object('fake_legacy_ep', 'fake_vf', [])
nfo = simics.map_info_t()
nfo.base = bdf << 12
nfo.length = (2 << 8) << 12  # map two busses
nfo.function = 42
nfo.priority = 2
map_ifc.map_simple(vf, None, nfo)

# check that we got the expected map entry in cfg_space
base = offset = bdf << 16
dev = rc.dp.impl.cfg_to_conf
size = nfo.length << 4
target = rc.dp.conf_space
priority = nfo.priority
exp_map_entry = [base, dev, 0, offset, size, target, priority, 0, 0]
stest.expect_true(exp_map_entry in rc.dp.cfg_space.map)

# test access into the first mapped bus
t = simics.transaction_t(write=True, size=1, value_le=random.randrange(256))
simics.SIM_issue_transaction(rc.dp.port.cfg, t, bdf << 16)
stest.expect_equal(vf.tx_addr, 0)
stest.expect_equal(vf.tx_val, t.value_le)
stest.expect_equal(vf.map_fun, 42)

# test access into the second mapped bus
test_bdf = (1 << 8) | random.randrange(256)
offset = random.randrange(1 << 12)
addr = ((bdf + test_bdf) << 16) + offset
exc = simics.SIM_issue_transaction(rc.dp.port.cfg, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(vf.tx_addr, (test_bdf << 12) + offset)

# bits 15:12 can't be represented, and are lost
addr |= 0xf000
simics.SIM_issue_transaction(rc.dp.port.cfg, t, addr)
stest.expect_equal(vf.tx_addr, (test_bdf << 12) + offset)

map_ifc.unmap(vf, None)
stest.expect_false(exp_map_entry in rc.dp.cfg_space.map)

# check that we can add maps to conf_space during init
bdf = random.randrange(256) << 8
dp = simics.pre_conf_object('meh', 'pcie-downstream-port-legacy')
base = bdf << 12
size = 1 << 8
dp.conf_space.map = [[bdf << 12, vf, 0, 0, 1 << 8]]
simics.SIM_add_configuration([dp], None)
dp = simics.SIM_get_object(dp.name)
base = base << 4
dev = dp.impl.cfg_to_conf
offset = base
size = size << 4
target = dp.conf_space
exp_map_entry = [base, dev, 0, offset, size, target, 0, 0, 0]
stest.expect_true(exp_map_entry in dp.cfg_space.map)
simics.SIM_delete_object(dp)

# test peer-to-peer cfg access, legacy conf_space allowed this
(b, d, f, ep) = (rc.dp.bus_number, *rc.dp.pci_devices[0][:-1])
legacy_addr = ((b << 8) | (d << 3) | f) << 12
offset = random.randrange(1 << 12)
simics.SIM_issue_transaction(rc.dp.conf_space, t, legacy_addr + offset)
stest.expect_equal(ep.tx_addr, offset)
stest.expect_equal(ep.tx_val, t.value_le)

# Test pci_bus_interface
ifc = rc.dp.iface.pci_bus

b = random.randrange(256)
mt = simics.SIM_new_map_target(rc.dp.port.cfg, None, None)
rc.dp.iface.pcie_port_control.set_secondary_bus_number(b)
for i, (df, o) in enumerate(rc.dp.functions):
    d = df >> 3
    f = df & 0x7
    rid = ((b << 8) | (d << 3) | f)
    mf_pdev = None
    if hasattr(o.iface, 'pcie_device'):
        continue
    if hasattr(o, 'ep'):
        mf_pdev = o.ep
        # test device bus address
        stest.expect_equal(ifc.get_bus_address(mf_pdev), (rid & ~0x7) << 12)
        stest.expect_equal(rc.dp.iface.pcie_map.get_device_id(mf_pdev), rid & ~0x7)
    else:
        # test device bus address
        stest.expect_equal(ifc.get_bus_address(o), rid << 12)
        stest.expect_equal(rc.dp.iface.pcie_map.get_device_id(o), rid)

    # test that config banks are mapped properly
    t = simics.transaction_t(size=1, write=True)
    length = 1 << 16
    base = rid << 16

    for offs in (-1, 0, random.randrange(length), length - 1, length):
        addr = base + offs
        val = random.randrange(256)
        t.value_le = val
        exc = simics.SIM_issue_transaction(mt, t, addr)
        if (offs >= 0 and offs < length):
            stest.expect_equal(exc, simics.Sim_PE_No_Exception)
            check(o, tx_val=val, tx_addr=offs, map_fun=255)
        else:
            # we might have hit another device so don't expect a miss
            # but make sure we didn't hit this device
            stest.expect_different(o.tx_val, val)
            stest.expect_different(o.tx_addr, offs)

    # test that we can enable/disable via pci_devices attribute
    for n, (_, _, obj, _) in enumerate(rc.dp.pci_devices):
        l = None
        if mf_pdev is None:
            if o == obj:
                l = [d, f, o, 0]
                break
        else:
            if obj == mf_pdev:
                l = [d, 0, obj, 0]
                break
    addr = (((b << 8) | (d << 3) | f) << 16)
    if mf_pdev is None:
        rc.dp.pci_devices[n] = l
        exc = simics.SIM_issue_transaction(mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)
        l[3] = 1
        rc.dp.pci_devices[n] = l
        exc = simics.SIM_issue_transaction(mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)

    # test that we can enable/disable via bus interface
    l[3] = 0
    ifc.set_device_status(d, f, 0)
    if mf_pdev is None:
        stest.expect_equal(rc.dp.pci_devices[n], l)
    exc = simics.SIM_issue_transaction(mt, t, addr)
    stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)
    ifc.set_device_status(d, f, 1)
    l[3] = 1
    if mf_pdev is None:
        stest.expect_equal(rc.dp.pci_devices[n], l)
    t.value_le = random.randrange(256)
    exc = simics.SIM_issue_transaction(mt, t, addr)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    check(o, map_fun=255, tx_val=t.value_le)

    # test legacy interrupt pins
    rid = (b << 8) | (d << 3) | f
    for pin in range(4):
        funcs = (ifc.raise_interrupt, ifc.lower_interrupt)
        codes = [base + pin for base in (simics.PCIE_Msg_Assert_INTA,
                                         simics.PCIE_Msg_Deassert_INTA)]
        for fun, msg in zip(funcs, codes):
            fun(o, pin)
            check(rc, tx_addr=0, tx_type=simics.PCIE_Type_Msg,
                  msg_type=msg, requester_id=rid)

    # test that hot_reset is translated to bus_reset
    rc.dp.iface.pcie_port_control.hot_reset()
    stest.expect_equal(o.bus_reset, True)
    o.bus_reset = False

# test add/remove map
mobj = simics.SIM_create_object('fake_legacy_ep', None, [])

spaces = {simics.Sim_Addr_Space_Conf:   ifc.configuration_space(),
          simics.Sim_Addr_Space_IO:     ifc.io_space(),
          simics.Sim_Addr_Space_Memory: ifc.memory_space()}


for (kind, ms) in spaces.items():
    for _ in range(3):
        if (kind == simics.Sim_Addr_Space_Conf):
            base = random.randrange(1 << 16) << 12
            length = random.randrange(1 << 25)
        else:
            base = random.randrange(1 << 32)
            length = random.randrange(1 << 32)
        nfo = simics.map_info_t(base=base,
                                length=length,
                                start=random.randrange(1 << 32),
                                function=random.randrange(1 << 31),
                                priority=random.randrange(-(1 << 15), 1 << 15))
        ifc.add_map(mobj, kind, None, nfo)

        for offs in (-1, 0, random.randrange(length), length - 1, length):
            addr = nfo.base + offs
            mop = simics.generic_transaction_t(
                physical_address=addr, data=bytes((val,)),
                type=simics.Sim_Trans_Store)

            if (offs >= 0 and offs < length):
                # test access in the 'upstream' memory-space
                ms.iface.memory_space.write(None, addr, (val,), 0)
                exp_addr = addr - nfo.base + nfo.start
                check(mobj, tx_val=val, tx_addr=exp_addr, map_fun=nfo.function)

                # test access in pci_downstream channel
                exc = rc.dp.iface.pci_downstream.operation(mop, kind)
                stest.expect_equal(exc, simics.Sim_PE_No_Exception)
                check(mobj, tx_val=val, tx_addr=exp_addr, map_fun=nfo.function)
            else:
                with stest.allow_log_mgr(log_type="error") if offs == length else nullcontext():
                    with stest.expect_exception_mgr(simics.SimExc_Memory):
                        ms.iface.memory_space.write(None, addr, (val,), 0)
                    exc = rc.dp.iface.pci_downstream.operation(mop, kind)
                    stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)

        ifc.remove_map(mobj, kind, nfo.function)
        with stest.expect_exception_mgr(simics.SimExc_Memory):
            ms.iface.memory_space.write(None, nfo.base, (val,), 0)
        mop = simics.generic_transaction_t(
            physical_address=nfo.base, size=1, type=simics.Sim_Trans_Store)
        exc = rc.dp.iface.pci_downstream.operation(mop, kind)
        stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)

for space, kind in ((simics.Sim_Addr_Space_Conf, simics.PCIE_Type_Cfg),
                    (simics.Sim_Addr_Space_IO, simics.PCIE_Type_IO),
                    (simics.Sim_Addr_Space_Memory, simics.PCIE_Type_Mem)):
    # Test upstream interface
    def random_addr():
        if kind == simics.PCIE_Type_Cfg:
            return random.randrange(1 << 28)
        else:
            return random.randrange(1 << 64)

    (d, f, ini) = pci_devices[0]
    addr = random_addr()
    rid = random.randrange(1 << 16)
    pasid = random.randrange(1 << 32)
    rc.tx_val = random.randrange(256)
    pmt = simics.pci_memory_transaction_t()
    pmt._internal_tlp_prefix = pasid
    pmt._internal_bus_address = rid << 12
    mop = pmt._internal_s
    mop.type = simics.Sim_Trans_Instr_Fetch
    mop.size = 1
    mop.ini_type = simics.Sim_Initiator_PCI_Device
    mop.ini_ptr = ini
    mop.physical_address = addr
    exc = rc.dp.iface.pci_upstream.operation(mop, space)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    stest.expect_equal(mop.value_le, rc.tx_val)
    exp_addr = new_addr(addr, space)  # Cfg space addresses are shifted
    check(rc, tx_type=kind, tx_addr=exp_addr, pasid=pasid, requester_id=rid)
    stest.expect_equal(rc.tx_flags, simics.Sim_Transaction_Fetch)

    # Set some attributes that should propagate to 'flags'
    mop.type = simics.Sim_Trans_Store
    mop.atomic = 1
    mop.inquiry = 1
    mop.non_coherent = 1

    addr = random_addr()
    val = random.randrange(256)
    mop.value_le = val
    mop.physical_address = addr
    pmt._internal_tlp_prefix = 0  # No PASID
    pmt._internal_bus_address = 0
    # Should get requester id from 'bus', using ini_ptr
    b = rc.dp.sec_bus_num
    rid = ((b << 8) | (d << 3) | f)
    exc = rc.dp.iface.pci_upstream.operation(mop, space)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    exp_addr = new_addr(addr, space)  # Cfg space addresses are shifted
    check(rc, tx_type=kind, tx_addr=exp_addr,
          tx_val=val, pasid=None, requester_id=rid)
    # Check the expected flags
    stest.expect_equal(rc.tx_flags,
                       simics.Sim_Transaction_Write |
                       simics.Sim_Transaction_Atomic |
                       simics.Sim_Transaction_Inquiry |
                       simics.Sim_Transaction_Incoherent)

    # Test upstream_operation interface
    addr = random_addr()
    rid = random.randrange(1 << 16)
    buf = simics.buffer_t(1)
    rc.tx_val = random.randrange(256)
    exc = rc.dp.iface.pci_upstream_operation.read(None, rid, space, addr, buf)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    stest.expect_equal(buf[0], rc.tx_val)
    exp_addr = new_addr(addr, space)  # Cfg space addresses are shifted
    check(rc, tx_type=kind, tx_addr=exp_addr, requester_id=rid)

    addr = random_addr()
    rid = random.randrange(1 << 16)
    buf = bytes((random.randrange(256),))
    exc = rc.dp.iface.pci_upstream_operation.write(None, rid, space, addr, buf)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    stest.expect_equal(rc.tx_val, buf[0])
    exp_addr = new_addr(addr, space)  # Cfg space addresses are shifted
    check(rc, tx_type=kind, tx_addr=exp_addr, requester_id=rid)

# Test pci_express interface for sending messages upstream
mtype = random.randrange(1 << 8)
(d, f, src) = random.sample(pci_devices, 1)[0]
rid = (rc.dp.sec_bus_num << 8) | (d << 3) | f
val = random.randrange(256)
ret = rc.dp.iface.pci_express.send_message(src, mtype, (val,))
stest.expect_equal(ret, 0)
check(rc, tx_type=simics.PCIE_Type_Msg, tx_val=val,
      msg_type=mtype, requester_id=rid)

# Test pci_express interface for sending messages downstream
mtype = random.randrange(1 << 8)
src = rc.dp.upstream_target
val = random.randrange(256)
ret = rc.dp.iface.pci_express.send_message(src, mtype, (val,))
stest.expect_equal(ret, 0)
for pdev in (d[1] for d in rc.dp.functions):
    check(pdev, msg_type=mtype, msg_data=(val,), msg_src=src)
check(rc, tx_type=None, tx_val=None, msg_type=None, requester_id=None)


# Test error message on missing message interface
class bad_ep:
    cls = simics.confclass('bad-ep')
    cls.iface.pci_device()
    cls.iface.io_memory()


(d, f, ldev, _) = rc.dp.pci_devices[-1]
bad = simics.SIM_create_object('bad-ep', 'bad_ep0')
rc.dp.pci_devices[-1] = [d, f, bad]
with stest.expect_log_mgr(log_type='error'):
    exc = simics.SIM_issue_transaction(rc.dp.port.downstream, t, addr)
stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)
rc.dp.pci_devices[-1] = [d, f, ldev]  # restore device list

# Test pci_express interface for receiving message in EP
(d, f, ldev, _) = rc.dp.pci_devices[-1]
lmsg = simics.SIM_create_object('legacy-message-ep', 'legacy_message_ep0')
rc.dp.pci_devices[-1] = [d, f, lmsg]
t = simics.transaction_t(pcie_type=simics.PCIE_Type_Msg,
                         pcie_msg_route=simics.PCIE_Msg_Route_ID,
                         pcie_msg_type=simics.PCIE_Vendor_Defined_Type_0,
                         initiator=rc,
                         data=b'cow')
addr = ((d << 3) | f) << 48
exc = simics.SIM_issue_transaction(rc.dp.port.downstream, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
check(lmsg,
      msg_type=t.pcie_msg_type,
      msg_data=tuple(t.data),
      msg_src=t.initiator)

# Test broadcasting, should reach all eps but with info-log about address
# bits not being forwarded to 'lmsg'
t.pcie_msg_route = simics.PCIE_Msg_Route_Broadcast
t.pcie_msg_type = simics.PCIE_Vendor_Defined_Type_1

for pdev in (d[2] for d in itertools.chain(rc.dp.pci_devices, rc.dp.devices)):
    pdev.msg_count = 0

exc = simics.SIM_issue_transaction(rc.dp.port.downstream, t, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)

for pdev in (d[2] for d in itertools.chain(rc.dp.pci_devices, rc.dp.devices)):
    check(pdev,
          msg_type=t.pcie_msg_type,
          msg_data=tuple(t.data),
          msg_src=t.initiator,
          msg_count=1)
    if hasattr(pdev, 'msg_addr'):
        check(pdev, msg_addr=0)

rc.dp.pci_devices[-1] = [d, f, ldev]  # restore device list

# Test port.pcie_message for receiving message in EP
(d, f, ldev, _) = rc.dp.pci_devices[0]
addr = ((d << 3) | f) << 48
exc = simics.SIM_issue_transaction(rc.dp.port.downstream, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
check(ldev,
      msg_type=t.pcie_msg_type,
      msg_data=tuple(t.data),
      msg_src=t.initiator,
      msg_addr=addr)
# Test sending message to new-style EP
(d, f, ndev) = rc.dp.devices[0]
addr = ((d << 3) | f) << 48
exc = simics.SIM_issue_transaction(rc.dp.port.downstream, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
check(ndev, msg_type=t.pcie_msg_type)


# Test 'upstream' port for sending messages
mtype = random.randrange(1 << 8)
addr = random.randrange(1 << 64)
t = simics.transaction_t(pcie_type=simics.PCIE_Type_Msg, pcie_msg_type=mtype)
mt = simics.SIM_new_map_target(rc.dp.port.upstream, None, None)
simics.SIM_issue_transaction(mt, t, addr)
check(rc, tx_type=simics.PCIE_Type_Msg, msg_type=mtype,
      tx_val=0, tx_addr=addr)


# Messaging with size 0 should work even if upstream_target implements
# io_memory, by padding the message before passing it on to upstream
class io_tgt:
    cls = simics.confclass('io-tgt')
    cls.attr.msg_type('i|n', default=None)
    cls.attr.size('i|n', default=None)

    @cls.iface.io_memory.operation
    def operation(self, memop, nfo):
        self.msg_type = memop.transaction.pcie_msg_type
        self.size = memop.transaction.size
        return simics.Sim_PE_No_Exception


rc.dp.upstream_target = simics.SIM_create_object('io-tgt', 'iotgt', [])
simics.SIM_issue_transaction(mt, t, addr)
check(rc.dp.upstream_target, msg_type=mtype, size=0)
rc.dp.upstream_target = rc
simics.SIM_free_map_target(mt)


# Test unimplemented methods
with stest.expect_log_mgr(log_type='unimpl'):
    ifc.set_bus_number(0)
with stest.expect_log_mgr(log_type='unimpl'):
    ifc.set_sub_bus_number(0)
with stest.expect_log_mgr(log_type='unimpl'):
    ifc.bus_reset()
with stest.expect_log_mgr(log_type='unimpl'):
    ifc.system_error()

# Test pci_multi_function_device_interface

# A device implementing pci_multi_function_device is allowed to be
# listed as device=0,function=0, even if another such device already
# exist. It may then use the 'supported_functions' method to claim
# any DeviceID on the "bus".
ldev = simics.SIM_create_object('fake_legacy_ep', None)
mfdev = simics.SIM_create_object('fake_legacy_mf_ep', 'mfdev')
mfdev.dev_id0 = 1
mfdev.dev_id1 = 1
mfdev.dev_id2 = 2
mf_funcs = [simics.SIM_create_object('fake_legacy_function', f'mfX_f{d}', [['ep', mfdev]])
           for d in range(3)]
mfdev.dev0 = mf_funcs[0]
mfdev.dev1 = mf_funcs[1]
mfdev.dev2 = mf_funcs[2]
rc.dp.devices = []
rc.dp.pci_devices = []
rc.dp.pci_devices = [[0, 0, ldev], [0, 0, mfdev]]

# The main object should not be mapped
stest.expect_false(mfdev in [me[1] for me in rc.dp.cfg_space.map])

# The objects provided via supported_functions should be mapped, and
# it should be possible to even specify the device number
for (bdf, dev) in [(8, mf_funcs[0]), (10, mf_funcs[1]), (20, mf_funcs[2])]:
    exp_map_entry = [bdf << 16, dev, 255, 0, 1 << 16, None, 0, 0, 0]
    stest.expect_true(exp_map_entry in rc.dp.cfg_space.map)

# Must not specify function when connecting an mf device
with stest.expect_log_mgr(log_type="error", regex=r"function.*must be 0"):
    rc.dp.pci_devices = [[0, 1, mfdev]]

# Must not specify device when connecting an mf device which uses
# 8-bit functions
with stest.expect_log_mgr(log_type="error", regex="illegal device:function"):
    rc.dp.pci_devices = [[3, 0, mfdev]]


class bad_mf_dev:
    cls = simics.confclass('bad-mf-dev')
    cls.iface.pci_device()
    cls.iface.io_memory()

    @cls.iface.pci_multi_function_device.supported_functions
    def supported_functions(self):
        return [[257, self.obj]]


bad_mfdev = simics.SIM_create_object('bad-mf-dev', 'bad_mfdev')

# Must not return function numbers bigger than 256
with stest.expect_log_mgr(log_type="error", regex=r"illegal function.*given"):
    rc.dp.pci_devices = [[0, 0, bad_mfdev]]
    rc.dp.pci_devices = []

# Must not use a multi-function-device which claims a function
# assigned to another device
with stest.expect_log_mgr(log_type="error", regex="duplicate"):
    rc.dp.pci_devices = [[0, 0, mfdev], [1, 2, ldev]]

# Requester id in mem_op when (legacy) for legacy interfaces of upstream DMAs
class legacy_ep:
    cls = simics.confclass('legacy-ep')
    cls.iface.pci_device()
    cls.iface.io_memory()

    def __init__(self):
        self.pci_bus = None

    def set_pci_bus(self, obj):
        self.pci_bus = obj

    def upstream_dma_io_memory(self, internal_bus_address=0):
        if self.pci_bus is None:
            raise Exception("No pci bus set")
        pmop = simics.pci_memory_transaction_t()
        mop = pmop._internal_s
        simics.SIM_set_mem_op_initiator(mop, simics.Sim_Initiator_PCI_Device, self.obj)
        simics.SIM_set_mem_op_type(mop, simics.Sim_Trans_Load)
        pmop._internal_bus_address = internal_bus_address
        nfo = simics.map_info_t()
        nfo.function = simics.Sim_Addr_Space_Memory
        self.pci_bus.iface.io_memory.operation(mop, nfo)

    def upstream_dma_pci_upstream(self, internal_bus_address=0):
        if self.pci_bus is None:
            raise Exception("No pci bus set")
        pmop = simics.pci_memory_transaction_t()
        mop = pmop._internal_s
        simics.SIM_set_mem_op_initiator(mop, simics.Sim_Initiator_PCI_Device, self.obj)
        simics.SIM_set_mem_op_type(mop, simics.Sim_Trans_Load)
        pmop._internal_bus_address = internal_bus_address
        self.pci_bus.iface.pci_upstream.operation(mop, simics.Sim_Addr_Space_Memory)


class upstream_tgt:
    cls = simics.confclass('upstream-tgt')
    cls.iface.io_memory()
    cls.attr.requester_id("i|n", default=None)

    @cls.iface.io_memory.operation
    def operation(self, mop, _nfo):
        pmop = simics.SIM_pci_mem_trans_from_generic(mop)
        self.requester_id = simics.VT_get_pci_mem_op_requester_id(pmop)
        return simics.Sim_PE_No_Exception

    @cls.attr.requester_id.getter
    def get_requester_id(self):
        requester_id = self.requester_id
        self.requester_id = None
        return requester_id

dp = simics.SIM_create_object('pcie-downstream-port-legacy', 'dp')
ut = simics.SIM_create_object('upstream-tgt', 'ut')
dp.upstream_target = ut
ep = simics.SIM_create_object('legacy-ep', 'ep')
ep.object_data.set_pci_bus(dp)
dp.pci_devices = [[20, 0, ep, 1]]
ep.object_data.upstream_dma_io_memory()
stest.expect_equal(ut.requester_id, 0xa0)
rid = random.randrange(1 << 16)
ep.object_data.upstream_dma_io_memory(rid << 12)
stest.expect_equal(ut.requester_id, rid)

ep.object_data.upstream_dma_pci_upstream()
stest.expect_equal(ut.requester_id, 0xa0)
