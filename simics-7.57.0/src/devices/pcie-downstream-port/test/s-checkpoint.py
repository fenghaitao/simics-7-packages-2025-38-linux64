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

import conf
import simics
import stest
import tempfile
import os


class initiator:
    cls = simics.confclass('initiator')

    cls.attr.target('o|n', default=None, optional=True)
    cls.attr.deferred('i|n', default=None, optional=True)
    cls.attr.value('i|n', default=None, optional=True)
    cls.attr.issue('i', pseudo=True, kind=simics.Sim_Attr_Write_Only)
    cls.attr.exc('i|n', default=None, optional=True)

    @cls.attr.target.setter
    def tset(self, val):
        simics.SIM_free_map_target(self.target)
        if val:
            self.target = simics.SIM_new_map_target(val, None, None)
        else:
            self.target = None

    @cls.attr.target.getter
    def tget(self):
        if self.target:
            return self.target.object
        return None

    @cls.attr.deferred.setter
    def dset(self, val):
        if val is None:
            self.deferred = None
        else:
            self.deferred = simics.transaction_t(
                size=1, completion=self.completion, owner=self.obj)
            simics.SIM_reconnect_transaction(self.deferred, val)

    @cls.attr.deferred.getter
    def dget(self):
        if self.deferred:
            return simics.SIM_get_transaction_id(self.deferred)
        return None

    @cls.attr.issue.setter
    def iset(self, val):
        self.deferred = simics.transaction_t(
            size=1, completion=self.completion, owner=self.obj)
        exc = simics.SIM_issue_transaction(self.target, self.deferred, val)
        self.exc = simics.SIM_monitor_transaction(self.deferred, exc)
        stest.expect_equal(self.exc, simics.Sim_PE_Deferred)

    def completion(self, obj, t, exc):
        stest.expect_equal(obj, self.obj)
        stest.expect_equal(t, self.deferred)
        self.value = t.value_le
        self.deferred = None
        self.exc = exc
        return exc


class endpoint:
    cls = simics.confclass('endpoint')

    cls.attr.deferred('i|n', default=None, optional=True)
    cls.attr.complete('i', pseudo=True, kind=simics.Sim_Attr_Write_Only)
    cls.attr.pcie_type('i|n', default=None, optional=True)
    cls.attr.pcie_device_id('i|n', default=None, optional=True)

    @cls.attr.deferred.setter
    def dset(self, val):
        if val is None:
            self.deferred = None
        else:
            self.deferred = simics.SIM_defer_transaction(self.obj, None)
            simics.SIM_reconnect_transaction(self.deferred, val)

    @cls.attr.deferred.getter
    def dget(self):
        if self.deferred is None:
            return None
        return simics.SIM_get_transaction_id(self.deferred)

    @cls.attr.complete.setter
    def complete_setter(self, val):
        stest.expect_equal(self.deferred.pcie_type, self.pcie_type)
        stest.expect_equal(self.deferred.pcie_device_id, self.pcie_device_id)

        self.deferred.value_le = val
        simics.SIM_complete_transaction(
            self.deferred, simics.Sim_PE_No_Exception)

    @cls.iface.transaction.issue
    def issue(self, t, offset):
        stest.expect_true(self.deferred is None)
        self.pcie_type = t.pcie_type
        self.pcie_device_id = t.pcie_device_id

        self.deferred = simics.SIM_defer_transaction(self.obj, t)
        stest.expect_true(self.deferred is not None)
        return simics.Sim_PE_Deferred


simics.SIM_create_object('pcie-downstream-port', 'dp', [])
simics.SIM_create_object('endpoint', 'ep', [])
simics.SIM_create_object('initiator', 'ini', [['target', conf.dp.port.msg]])
conf.dp.msg_space.default_target = [conf.ep, 0, 0, None]

conf.ini.issue = 42 << 48
stest.expect_equal(conf.ini.exc, simics.Sim_PE_Deferred)
stest.expect_equal(len(conf.dp.chained_transactions), 1)

with tempfile.TemporaryDirectory() as tmpdir:
    cpfile = os.path.join(tmpdir, "pcie-downstream-port.cp")
    simics.SIM_write_configuration_to_file(cpfile, 0)
    simics.SIM_delete_objects([conf.dp, conf.ep, conf.ini])

    simics.SIM_read_configuration(cpfile)

stest.expect_equal(len(conf.dp.chained_transactions), 1)
conf.ep.complete = 33
stest.expect_equal(conf.ini.value, 33)
stest.expect_equal(conf.ini.exc, simics.Sim_PE_No_Exception)
stest.expect_equal(conf.ep.pcie_type, simics.PCIE_Type_Msg)
stest.expect_equal(conf.ep.pcie_device_id, 42)

stest.expect_equal(len(conf.dp.chained_transactions), 0)

with stest.expect_exception_mgr(simics.SimExc_IllegalValue):
    conf.dp.chained_transactions = [[0, 0, 0]]
