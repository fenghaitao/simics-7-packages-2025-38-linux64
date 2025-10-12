# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from configuration import *
import stest

SIM_create_object("clock", "clock0", freq_mhz=1)

SIM_load_module('signal-link')
SIM_load_module('sample-signal-device')

def cmd(x):
    try:
        return run_command(x)
    except CliError as msg:
        raise Exception("Failed running '%s': %s" % (x, msg))

def connect(c1, c2):
    cmd("connect %s %s" % (c1, c2))

def disconnect(c1, c2):
    cmd("disconnect %s %s" % (c1, c2))

def test_get_free_connector():
    cmd("create-signal-link link0")
    # Test connect
    senders = 4
    receivers = 10

    for x in range(senders):
        cmd("create-sample-signal-device dev_sender%s" % x)
        signal_sender_connector = cmd("link0.get-free-sender-connector")
        connect(signal_sender_connector, "dev_sender%s.out" % x)
    for x in range(receivers):
        cmd("create-sample-signal-device dev_receiver%s" % x)
        signal_receiver_connector = cmd("link0.get-free-receiver-connector")
        connect(signal_receiver_connector, "dev_receiver%s.in" % x)

    # Test disconnect
    for x in range(senders):
        disconnect("link0.sender%s" % x, "dev_sender%s.out" % x)
    for x in range(receivers):
        disconnect("link0.receiver%s" % x, "dev_receiver%s.in" % x)

test_get_free_connector()
print("s-get-free-connector: all tests passed")
