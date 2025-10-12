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


# s-spi-prog-access.py
# tests the programming register accessing of SPI flash in the ICH9

# this test case using M25Pxx to test misc command
# such as: WRSR,RDSR,DP,RES.

from tb_spi import *

import random

ssfc_off    = Ich9SpiConst.reg_info["SSFC"][0]
ssfc_bits   = Ich9SpiConst.reg_info["SSFC"][1] * 8
ssfs_off    = Ich9SpiConst.reg_info["SSFS"][0]
ssfs_bits   = Ich9SpiConst.reg_info["SSFS"][1] * 8
ssfs_clear  = ssfs_bf.value(CDS = 1)
fdata0_off  = Ich9SpiConst.reg_info["FDATA0"][0]
faddr_off   = Ich9SpiConst.reg_info["FADDR"][0]


def test_flash_status_reg(bar):

    # 1) Test the write status command
    W_NUM = 0
    R_NUM = 0
    r_ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = R_NUM,
                         COP = M25p80Const.read_status_index,
                         SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         ACS = 0, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, r_ctrl)
    status_r = tb.read_value_le(bar + fdata0_off, 32)

    # Fake flash status data and put it to buffer-register
    BPx = 0x14  #ie. BP2=1,BP1=0,BP0=1
    status_w = status_r | BPx
    tb.write_value_le(bar + fdata0_off, 32, status_w)

    #NOTE: need to set ACS = 1 if want to send pre-opcode
    w_ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = W_NUM,
                         COP = M25p80Const.write_status_index,
                         SPOP = ICH9_SPI_WRITE_EN_PREFIX,
                         ACS = 1, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, w_ctrl)

    # read back to examine:
    # first clear the FDATA0 for read
    tb.clear_fdata_regs(bar, 16)

    # then read
    tb.write_value_le(bar + ssfc_off, ssfc_bits, r_ctrl)
    status_r = tb.read_value_le(bar + fdata0_off, 32)

    # now examine the SPI status register again:
    expect(status_r & BPx, BPx, "Flash status reg's BPx bits")



def test_dp_res_command(bar):
    # 1) Test the write status command
    ctrl_dp = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 0, DBC = 0,
                         COP = M25p80Const.deep_mode_index,
                         SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         ACS = 0, SCGO = 1)
    ctrl_res = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = 3,
                         COP = M25p80Const.release_dp_index,
                         SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         ACS = 0, SCGO = 1)

    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl_dp)

    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl_res)
    ele_sig = tb.read_value_le(bar + fdata0_off, 32)
    read_out = list(dev_util.value_to_tuple_le(ele_sig,4))
    expect=[0x0,0x0,0x0,0x13]
    expect_list(read_out, expect, "electronic signature")

    ####### follow read out value dot no need verified
    tb.write_value_le(bar + fdata0_off, 32, 0)
    ctrl_res = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 0, DBC = 3,
                             COP = M25p80Const.release_dp_index,
                             SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                             ACS = 0, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl_res)
    tb.read_value_le(bar + fdata0_off, 32)   # ele_sig

def test_uint(bar):
    test_flash_status_reg(bar)
    test_dp_res_command(bar)

def do_test():
    test_uint(SPIBAR)
    test_uint(GBEBAR)

tb = TestBench(1, True, False)
do_test()
