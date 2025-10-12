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


import cli

#
# -------------------- e1000_spi info and status commands ----------------
#

def e1000_spi_get_info(obj):
    return [ ("Connection",
              [("SPI slave device", obj.spi_slave) ] ) ]

def e1000_spi_get_status(obj):
    return [ ("State",
              [ ("Status of inner state-machine", obj.x_state),
                ("Current master that using SPI bus lines", obj.cur_master_idx)] ) ]

cli.new_info_command("e1000_spi", e1000_spi_get_info)
cli.new_status_command("e1000_spi", e1000_spi_get_status)
