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


import simics
import stest
import pyobj
import comp
import random
random.seed("Barbara Dane")


class fake_pcie_device(pyobj.ConfObject):
    class tx_addr(pyobj.SimpleAttribute(None, 'i|n')): pass
    class tx_type(pyobj.SimpleAttribute(None, 'i|n')): pass
    class tx_val(pyobj.SimpleAttribute(None, 'i|n')): pass
    class device_id(pyobj.SimpleAttribute(None, 'i|n')): pass
    class requester_id(pyobj.SimpleAttribute(None, 'i|n')): pass
    class msg_addr(pyobj.SimpleAttribute(None, 'i|n')): pass
    class msg_data(pyobj.SimpleAttribute(None, 'd|n')): pass
    class msg_src(pyobj.SimpleAttribute(None, 'o|n')): pass
    class msg_type(pyobj.SimpleAttribute(None, 'i|n')): pass
    class msg_count(pyobj.SimpleAttribute(0, 'i|n')): pass
    class ut(pyobj.SimpleAttribute(None, 'o|n')): pass

    class dp(pyobj.PortObject):
        namespace = None
        classname = 'pcie-downstream-port'

    class pcie_device(pyobj.Interface):
        def hot_reset(self): pass

        def connected(self, ut, devid):
            self._top.ut.setter(ut)
            ut.iface.pcie_map.add_function(self._top.obj, devid)

        def disconnected(self, ut, devid):
            ut.iface.pcie_map.del_function(self._top.obj, devid)
            self._top.ut.setter(None)

    class transaction(pyobj.Interface):
        def issue(self, t, addr):
            self._top.tx_addr.val = addr
            ptype = getattr(t, 'pcie_type', None)
            self._top.tx_type.val = ptype
            self._top.device_id.val = getattr(t, 'pcie_device_id', None)
            self._top.requester_id.val = getattr(t, 'pcie_requester_id', None)
            if ptype == simics.PCIE_Type_Msg:
                self._top.msg_type.val = t.pcie_msg_type
                self._top.msg_data.val = tuple(t.data)
                self._top.msg_src.val = t.initiator
                self._top.msg_addr.val = addr
                if self._top.msg_count.val is None:
                    self._top.msg_count.val = 0
                self._top.msg_count.val += 1
            elif simics.SIM_transaction_is_read(t):
                simics.SIM_set_transaction_value_le(t, self._top.tx_val.val)
            else:
                self._top.tx_val.val = t.value_le
            return simics.Sim_PE_No_Exception

    def _initialize(self):
        pyobj.ConfObject._initialize(self)
        dp = simics.SIM_object_descendant(self.obj, 'dp')
        simics.SIM_set_attribute_default(dp, 'upstream_target', self.obj)


class rc_with_switch(comp.StandardComponent):
    def setup(self):
        self.add_pre_obj('clock', 'clock', freq_mhz=1)
        rc = self.add_pre_obj('root_complex', 'fake_pcie_device')
        sw = self.add_pre_obj('switch', 'fake_pcie_device')
        rc.dp.devices = [[0, sw]]
        bridges = self.add_pre_obj(
            'internal_bridge[3]', 'fake_pcie_device')
        sw.dp.devices = [[i, i, b] for (i, b) in enumerate(bridges)]
        ep = self.add_pre_obj('endpoint[10]', 'fake_pcie_device')
        bridges[0].dp.devices = [[0, 0, ep[0]]]
        bridges[1].dp.devices = [[0, 0, ep[1]]]
        bridges[2].dp.devices = [[0, i, f] for (i, f) in enumerate(ep[2:])]


class rc_with_eps(comp.StandardComponent):
    def setup(self):
        self.add_pre_obj('clock', 'clock', freq_mhz=1)
        rc = self.add_pre_obj('rc', 'fake_pcie_device')
        eps = self.add_pre_obj('ep[3]', 'fake_pcie_device')
        bdfs = random.sample(range(1 << 8), len(eps))
        rc.dp.devices = [[bdf, ep] for (bdf, ep) in zip(bdfs, eps)]


class fake_legacy_rc(fake_pcie_device):
    class pasid(pyobj.SimpleAttribute(None, 'i|n')): pass
    class tx_flags(pyobj.SimpleAttribute(None, 'i|n')): pass
    class transaction(fake_pcie_device.transaction):
        def issue(self, t, addr):
            self._top.pasid.val = getattr(t, 'pcie_pasid', None)
            self._top.tx_flags.val = getattr(t, 'flags', None)
            if t.pcie_type == simics.PCIE_Type_Msg:
                self._top.tx_val.val = t.value_le
            return fake_pcie_device.transaction.issue(self, t, addr)
    class dp(fake_pcie_device.dp):
        classname = 'pcie-downstream-port-legacy'


class fake_legacy_ep:
    cls = simics.confclass('fake_legacy_ep')
    cls.attr.tx_addr('i|n', default=None)
    cls.attr.tx_val('i|n', default=None)
    cls.attr.map_fun('i|n', default=None)
    cls.attr.bus_reset('i|n', default=None)
    cls.attr.msg_src('o|n', default=None)
    cls.attr.msg_addr('i|n', default=None)
    cls.attr.msg_type('i|n', default=None)
    cls.attr.msg_data('d|n', default=None)
    cls.attr.msg_count('i|n', default=None)

    @cls.iface.pci_device.bus_reset
    def bus_reset(self):
        self.bus_reset = True

    @cls.iface.io_memory.operation
    def operation(self, mop, nfo):
        self.tx_addr = mop.physical_address - nfo.base + nfo.start
        self.map_fun = nfo.function
        if simics.SIM_mem_op_is_write(mop):
            self.tx_val = simics.SIM_get_mem_op_value_le(mop)
        else:
            simics.SIM_set_mem_op_value_le(mop, self.tx_val)
        return simics.Sim_PE_No_Exception

    pmsg = cls.o.port.pcie_message()

    @pmsg.iface.transaction.issue
    def issue(self, t, addr):
        if getattr(t, "pcie_type", None) == simics.PCIE_Type_Msg:
            self.msg_src = t.initiator
            self.msg_type = t.pcie_msg_type
            self.msg_addr = addr
            self.msg_data = tuple(t.data)
            if self.msg_count is None:
                self.msg_count = 0
            self.msg_count += 1
            return simics.Sim_PE_No_Exception
        return simics.Sim_PE_IO_Not_Taken


class fake_legacy_mf_ep:
    cls = simics.confclass('fake_legacy_mf_ep')
    cls.iface.pci_device()
    cls.iface.io_memory()
    cls.attr.dev_id0('i', default=0)
    cls.attr.dev_id1('i', default=0)
    cls.attr.dev_id2('i', default=0)

    cls.attr.dev0('o', default=None)
    cls.attr.dev1('o', default=None)
    cls.attr.dev2('o', default=None)

    @cls.iface.pci_device.bus_reset
    def bus_reset(self):
        self.dev0.bus_reset = True
        self.dev1.bus_reset = True
        self.dev2.bus_reset = True

    @cls.iface.pci_multi_function_device.supported_functions
    def supported_functions(self):
        return [[(self.dev_id0 << 3) | 0, self.dev0],
                [(self.dev_id1 << 3) | 2, self.dev1],
                [(self.dev_id2 << 3) | 4, self.dev2]]

class fake_legacy_function:
    cls = simics.confclass('fake_legacy_function')
    cls.iface.transaction()
    cls.attr.ep('o|n', default=None)
    cls.attr.bus_reset('i|n', default=None)
    cls.attr.tx_addr('i|n', default=None)
    cls.attr.tx_val('i|n', default=None)
    cls.attr.map_fun('i|n', default=None)
    cls.attr.msg_src('o|n', default=None)
    cls.attr.msg_type('i|n', default=None)
    cls.attr.msg_data('d|n', default=None)
    cls.attr.msg_addr('i|n', default=None)

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        self.tx_addr = addr
        self.map_fun = 255
        ptype = getattr(t, 'pcie_type', None)
        if ptype == simics.PCIE_Type_Msg:
            self.msg_type = t.pcie_msg_type
            self.msg_data = tuple(t.data)
            self.msg_src = t.initiator
            self.msg_addr = addr
        elif simics.SIM_transaction_is_read(t):
            simics.SIM_set_transaction_value_le(t, self.tx_val)
        else:
            self.tx_val = t.value_le
        return simics.Sim_PE_No_Exception


class legacy_message_ep:
    cls = simics.confclass('legacy-message-ep')
    cls.attr.msg_src('o|n', default=None)
    cls.attr.msg_type('i|n', default=None)
    cls.attr.msg_data('d|n', default=None)
    cls.attr.msg_count('i|n', default=None)
    cls.iface.pci_device()
    cls.iface.io_memory()

    @cls.iface.pci_express.send_message
    def send_message(self, src, mtype, payload):
        self.msg_src = src
        self.msg_type = mtype
        self.msg_data = payload
        if self.msg_count is None:
            self.msg_count = 0
        self.msg_count += 1
        return 0


def legacy_rc(name=None):
    rc = simics.SIM_create_object('fake_legacy_rc', name, [])
    legacy_eps = [simics.SIM_create_object('fake_legacy_ep', f'legacy_ep{d}')
                  for d in range(3)]
    legacy_mf_ep = simics.SIM_create_object('fake_legacy_mf_ep', f'legacy_mf_ep')
    mf_funcs = [simics.SIM_create_object('fake_legacy_function', f'mf_f{d}', [['ep', legacy_mf_ep]])
               for d in range(3)]
    legacy_mf_ep.dev0 = mf_funcs[0]
    legacy_mf_ep.dev1 = mf_funcs[1]
    legacy_mf_ep.dev2 = mf_funcs[2]

    new_eps = [simics.SIM_create_object('fake_pcie_device', f'new_ep{d}')
               for d in range(3)]
    bdfs = random.sample(range(0x100), len(legacy_eps + new_eps) + 1)
    pci_devices = [pci_attr(bdfs.pop(), dev) for dev in legacy_eps]
    pci_devices += [[(bdfs.pop() >> 3) & 31, 0, legacy_mf_ep]]
    new_devices = [pci_attr(bdfs.pop(), dev) for dev in new_eps]
    rc.dp.pci_devices = pci_devices
    rc.dp.devices = new_devices
    return rc, pci_devices


def pci_attr(fid, obj):
    return [(fid >> 3) & 31, fid & 7, obj]


def new_addr(addr, kind):
    if kind == simics.Sim_Addr_Space_Conf:
        # device id bits are shifted to 31:16 in new PCIe Config space
        return (addr & 0xffff000) << 4 | (addr & 0xfff)
    else:
        return addr


def check(obj, **attrs):
    for k, v in attrs.items():
        stest.expect_equal(getattr(obj, k), v, f"unexpected '{k}' in {obj}")
        setattr(obj, k, None)


def check_maps(dp, eps):
    # Config-space is mapped at 23:16 without offset
    cfg = [[did << 16, obj, 0, 0, 1 << 16, None, 0, 0, 0]
           for (obj, did) in eps]
    # Message-space is mapped at 53:48 with offset
    msg = [[did << 48, obj, 0, did << 48, 1 << 48, None, 0, 0, 0]
           for (obj, did) in eps]
    stest.expect_equal(sorted(dp.cfg_space.map), cfg)
    stest.expect_equal(sorted(dp.msg_space.map), msg)
