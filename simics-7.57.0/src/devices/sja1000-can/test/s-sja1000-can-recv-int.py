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


import dev_util
import conf
import stest
import sja1000_can_common
import cli

tb = sja1000_can_common.TestBench(2)

#-------------------config sender------------------------
#into reset mode
cli.run_command("mems0.write address = 0 size = 1 value = 0x01 -l")
#into Pelican mode
cli.run_command("mems0.write address = 31 size = 1 value = 0x80 -l")
#into operation mode
cli.run_command("mems0.write address = 0 size = 1 value = 0x00 -l")
#compound a TX frame
cli.run_command("mems0.write address = 16 size = 1 value = 0x03 -l")  #frm info
cli.run_command("mems0.write address = 17 size = 1 value = 0x40 -l")  #id1
cli.run_command("mems0.write address = 18 size = 1 value = 0x80 -l")  #id2
cli.run_command("mems0.write address = 19 size = 1 value = 0x55 -l")  #data1
cli.run_command("mems0.write address = 20 size = 1 value = 0x66 -l")  #data2
cli.run_command("mems0.write address = 21 size = 1 value = 0x77 -l")  #data2

#-------------------config receiver------------------------
#into reset mode
cli.run_command("mems1.write address = 0 size = 1 value = 0x01 -l")
#into Pelican mode
cli.run_command("mems1.write address = 31 size = 1 value = 0x80 -l")
#into reset mode for Peli
cli.run_command("mems1.write address = 0 size = 1 value = 0x01 -l")
#acceptance mask: accept all the recv frames
cli.run_command("mems1.write address = 20 size = 1 value = 0xff -l")
cli.run_command("mems1.write address = 21 size = 1 value = 0xff -l")
cli.run_command("mems1.write address = 22 size = 1 value = 0xff -l")
#into operation mode
cli.run_command("mems1.write address = 0 size = 1 value = 0x00 -l")
#enable receive interrupt
cli.run_command("mems1.write address = 4 size = 1 value = 0x01 -l")
#enable transmit interrupt
cli.run_command("mems0.write address = 4 size = 1 value = 0x02 -l")

#launch transmission
cli.run_command("mems0.write address = 1 size = 1 value = 0x01 -l")
#check the transmit interrupt
#after read, transmit interrupt will be reset
stest.expect_equal(conf.irq0.irq_cnt, 1)
ir = cli.run_command("mems0.read address = 3 size = 1 -l")
stest.expect_equal(conf.irq0.irq_cnt, 0)
stest.expect_equal(ir&0x1, 0x00)
SIM_continue(1)

#check the interrupt flags
stest.expect_equal(conf.irq1.irq_cnt, 1)
ir = cli.run_command("mems1.read address = 3 size = 1 -l")
stest.expect_equal(ir&0x1, 0x01)

#release receive buffer
cli.run_command("mems1.write address = 1 size = 1 value = 0x04 -l")
stest.expect_equal(conf.irq1.irq_cnt, 0)
ir = cli.run_command("mems1.read address = 3 size = 1 -l")
stest.expect_equal(ir&0x1, 0x00)
