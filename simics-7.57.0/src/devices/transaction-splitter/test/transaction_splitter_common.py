# © 2024 Intel Corporation
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
import pyobj

class txn_info:
    def __init__(self, s, a, v):
        self.size = s
        self.addr = a
        self.value = v

class dummy_device(pyobj.ConfObject):
    def clear_txns(self):
        self.received_txns = []

    class transaction(pyobj.Interface):
        def issue(self, t, addr):
            ti = txn_info(simics.SIM_transaction_size(t),
                          addr,
                          simics.SIM_get_transaction_value_le(t))
            self._up.received_txns.append(ti)
            return simics.Sim_PE_No_Exception

def create_transaction_splitter(name = None):
    '''Create a new transaction_splitter object'''
    ns = simics.pre_conf_object(name, 'namespace')
    ns.mem = simics.pre_conf_object('memory-space')
    ns.transaction_splitter = simics.pre_conf_object('transaction_splitter')
    ns.transaction_receiver = simics.pre_conf_object('dummy_device')
    ns.transaction_splitter.target = ns.transaction_receiver
    ns.mem.map = [[0x30, ns.transaction_splitter, 0, 0, 0x100]]
    simics.SIM_add_configuration([ns], None)
    return (simics.SIM_get_object(ns.mem.name),
            simics.SIM_get_object(ns.transaction_splitter.name),
            simics.SIM_get_object(ns.transaction_receiver.name))
