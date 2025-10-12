# © 2010 Intel Corporation
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
import os
import simics
import stest
import pyobj
import cli

records = ['Arinc-429 time-value pairs record of bus bus\n',
           'cycle 0 data 0x00000000\n',
           'cycle 100 data 0x00000001\n',
           'cycle 200 data 0x00000002\n',
           'cycle 300 data 0x00000003\n',
           'cycle 400 data 0x00000004\n',
           'cycle 500 data 0x00000005\n',
           'cycle 600 data 0x00000006\n',
           'cycle 700 data 0x00000007\n',
           'cycle 800 data 0x00000008\n',
           'cycle 900 data 0x00000009\n']

class simple_receiver(pyobj.ConfObject):
    '''A fake arinc429-bus simple receiver for testing'''
    def _initialize(self):
        super()._initialize()
        self.last_word = 0
        self.last_parity_ok = 0
        self.received_words = 0

    class arinc429_receiver(pyobj.Interface):
        def receive_word(self, data, parity_ok):
            self._up.last_word = data
            self._up.last_parity_ok = parity_ok
            self._up.received_words += 1

def create_basic_objects():
    simics.SIM_create_object("clock", "cpu", freq_mhz=1)
    simics.SIM_create_object("arinc429_bus", "bus", queue=conf.cpu)

def create_simple_receiver(serial_no=[0]):
    objname = "receiver%d" % serial_no[0]
    serial_no[0] += 1
    obj = simics.SIM_create_object("simple_receiver", objname)
    return obj

def test_many_receivers():
    rec1 = create_simple_receiver()
    rec2 = create_simple_receiver()

    conf.bus.receivers = [rec1, rec2]
    for i, (tx_word, tx_flag, rx_word, rx_flag) in enumerate([
        (0x1111, -1, 0x00001111, 0),
        (0x1111,  1, 0x80001111, 1),
        (0x1111,  0, 0x00001111, 0),
        (0x1110, -1, 0x00001110, 1),
        (0x1110,  1, 0x00001110, 1),
        (0x1110,  0, 0x80001110, 0)]):
        conf.bus.iface.arinc429_bus.send_word(tx_word, tx_flag)
        stest.expect_equal(rec1.object_data.last_word, rx_word)
        stest.expect_equal(rec1.object_data.last_parity_ok, rx_flag)
        stest.expect_equal(rec2.object_data.last_word, rx_word)
        stest.expect_equal(rec2.object_data.last_parity_ok, rx_flag)
        stest.expect_equal(rec1.object_data.received_words, i + 1)
        stest.expect_equal(rec2.object_data.received_words, i + 1)

def test_record_playback():
    rec1 = create_simple_receiver()
    conf.bus.receivers = [rec1]

    rec_file = os.path.join(os.environ.get('SANDBOX', '.'), 'recorded1.txt')
    if os.path.exists(rec_file):
        os.remove(rec_file)
    cli.run_command("bus.capture-start %s" % rec_file)

    for i in range(10):
        conf.bus.iface.arinc429_bus.send_word(i, -1)
        simics.SIM_continue(100)

    stest.expect_equal(rec1.object_data.last_word, 9)
    stest.expect_equal(rec1.object_data.received_words, 10)

    cli.run_command("bus.capture-stop")

    cli.run_command("bus.playback-start %s" % rec_file)

    simics.SIM_continue(550)
    stest.expect_equal(rec1.object_data.last_word, 5)
    stest.expect_equal(rec1.object_data.received_words, 16)

    cli.run_command("bus.playback-stop")

    simics.SIM_continue(500)

    stest.expect_equal(rec1.object_data.received_words, 16)

    rec_fileobj = open(rec_file, "r")
    lines = rec_fileobj.readlines()
    stest.expect_equal(lines, records)
    rec_fileobj.close()

create_basic_objects()
test_many_receivers()
test_record_playback()

print("Test passed.")
