# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test the simple interrupt to signal converter.

import sys, os
sys.path.append(os.path.join('..', 'common'))
import dev_util
import stest
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0

def test_signal_forwarding():
    int_to_sig = pre_conf_object('int_to_sig', 'interrupt_to_signal')
    signal_dev_ports = dev_util.Dev([('signal_port%d' % i,
                                      dev_util.Signal) for i in range(8)])
    signal_dev_object = dev_util.Dev([dev_util.Signal])
    signal_ports = [signal_dev_ports.signal_port0.signal,
                    signal_dev_ports.signal_port1.signal,
                    signal_dev_ports.signal_port2.signal,
                    signal_dev_ports.signal_port3.signal,
                    signal_dev_ports.signal_port4.signal,
                    signal_dev_ports.signal_port5.signal,
                    signal_dev_ports.signal_port6.signal,
                    signal_dev_ports.signal_port7.signal,
                    signal_dev_object.signal]
    int_to_sig.signal_targets = [[1, signal_dev_ports.obj, 'signal_port0', 0],
                                 [2, signal_dev_ports.obj, 'signal_port1', 0],
                                 [3, signal_dev_ports.obj, 'signal_port2', 0],
                                 [4, signal_dev_ports.obj, 'signal_port3', 0],
                                 [5, signal_dev_ports.obj, 'signal_port4', 0],
                                 [6, signal_dev_ports.obj, 'signal_port5', 0],
                                 [7, signal_dev_ports.obj, 'signal_port6', 0],
                                 [8, signal_dev_ports.obj, 'signal_port7', 0],
                                 [9, signal_dev_object.obj, None, 0]]
    SIM_add_configuration([int_to_sig], None)
    int_to_sig = conf.int_to_sig

    def check_signal_port_level(port_no, expected_level):
        stest.expect_equal(signal_ports[port_no].level, expected_level,
                           'unexpected level of signal_ports[%d]' % (port_no,))

    for port_no in range(9):
        check_signal_port_level(port_no, 0)
        int_to_sig.iface.simple_interrupt.interrupt(port_no + 1)
        check_signal_port_level(port_no, 1)
        for port_no2 in range(9):
            if port_no2 != port_no:
                check_signal_port_level(port_no2, 0)
        int_to_sig.iface.simple_interrupt.interrupt_clear(port_no + 1)
        check_signal_port_level(port_no, 0)

def test_hotplugging():
    signal = dev_util.Dev([dev_util.Signal])
    signal2 = dev_util.Dev([dev_util.Signal])
    int_to_sig = SIM_create_object(
        'interrupt_to_signal', None,
        [["signal_targets", [[0, signal.obj, None, 0]]]])

    # changing level by a simple attribute write has no side-effect
    int_to_sig.signal_targets[0][3] = 1
    stest.expect_equal(signal.signal.level, 0)
    signal.signal.level = 1

    # disconnecting a device with signal high lowers the level
    int_to_sig.signal_targets = []
    stest.expect_equal(signal.signal.level, 0)

    # connecting a device with signal high raises the level
    int_to_sig.signal_targets = [[0, signal.obj, None, 1]]
    stest.expect_equal(signal.signal.level, 1)

    # obscure: exchanging the places of two objects counts as
    # hotplugging
    int_to_sig.signal_targets = [[0, signal.obj, None, 1],
                                 [1, signal2.obj, None, 0]]
    signal.signal.level = 1
    signal2.signal.level = 0
    int_to_sig.signal_targets = [[0, signal2.obj, None, 1],
                                 [1, signal.obj, None, 0]]
    stest.expect_equal((signal.signal.level, signal2.signal.level), (0, 1))

def test_raise_on_creation():
    '''Signal is raised if the interrupt-to-signal device is created
    with the signal level high, unless restoring a checkpoint'''
    int_to_sig = pre_conf_object('int_to_sig1', 'interrupt_to_signal')
    signal = dev_util.Dev([dev_util.Signal])
    int_to_sig.signal_targets = [[0, signal.obj, None, 1]]
    SIM_add_configuration([int_to_sig], None)
    # i2s device created with level high, so the target needs to be
    # notified
    stest.expect_equal(signal.signal.level, 1)
    signal.signal.level = 0

    int_to_sig = pre_conf_object('int_to_sig2', 'interrupt_to_signal')
    int_to_sig.signal_targets = [[0, signal.obj, None, 1]]
    # simulate restoring a checkpoint. In this case the signal may not
    # be raised.
    VT_set_restoring_state(True)
    SIM_add_configuration([int_to_sig], None)
    VT_set_restoring_state(False)
    stest.expect_equal(signal.signal.level, 0)

test_signal_forwarding()
test_hotplugging()
test_raise_on_creation()

print('Test passed without errors')
