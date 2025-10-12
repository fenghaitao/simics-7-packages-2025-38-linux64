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


# s-spi-reset.py
# test the reset status of the SPI interface in the ICH9

from tb_spi import *

def regsSPI_test():
    for reg_name in list(Ich9SpiConst.reg_info.keys()):
        (off, len, def_val) = Ich9SpiConst.reg_info[reg_name]

        # because: 1) #FREG0/1/2/3/4 's value is load from flash ROM's content
        # 2) read "FDOD" will invoke spi-bus transaction and effect status register;
        if (reg_name[0:4] == "FREG") or (reg_name == "FDOD"):
            continue

        reg_val = tb.read_value_le(SPIBAR + off, len * 8)
        expect_hex(reg_val, def_val,
                   "default value of register %s in the SPI" % reg_name)

def regsGBE_test():
    for reg_name in list(Ich9SpiConst.gbe_regs_info.keys()):
        (off, len, def_val) = Ich9SpiConst.reg_info[reg_name]

        # because: 1) #FREG0/1/2/3/4 's value is load from flash ROM's content
        # 2) read "FDOD" will invoke spi-bus transaction and effect status register;
        if ((reg_name[0:4] == "FREG") or (reg_name == "FDOD")
                or (reg_name == "FRACC")):
            continue

        reg_val = tb.read_value_le(GBEBAR + off, len * 8)
        expect_hex(reg_val, def_val,
                   "default value of register %s in the GBE" % reg_name)

def regsSpi_test():
    for reg_name in list(Ich9SpiConst.reg_info.keys()):

        (off, len, def_val) = Ich9SpiConst.reg_info[reg_name]

        # because: 1) #FREG0/1/2/3/4 's value is load from flash ROM's content
        # 2) read "FDOD" will invoke spi-bus transaction and effect status register;
        if (reg_name[0:4] == "FREG") or (reg_name == "FDOD"):
            continue

        reg_val = tb.read_value_le(SPIBAR + off, len * 8)
        expect_hex(reg_val, def_val,
                   "default value of register %s in the SPI" % reg_name)

def do_test():
    regsSPI_test()
    regsGBE_test()

tb = TestBench(1, False, True)
do_test()
