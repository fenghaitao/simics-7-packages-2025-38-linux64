# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util as du
import conf
import simics

# SIMICS-21543
conf.sim.deprecation_level = 0

class dummy_spi_master(du.iface("serial_peripheral_interface_master")):
    def spi_response(self, sim_obj, bits, payload):
        print("Got response of %d bits" % bits)

# Create flash #0
flash_image0 = simics.pre_conf_object('flash_image0', 'image')
flash_image0.size = 32 * 1024 * 1024
flash_image0.init_pattern = 0xFF
flash0 = simics.pre_conf_object('flash0', 'generic_spi_flash')
flash0.mem_block = flash_image0
flash0.elec_signature = 0x17
flash0.JEDEC_signature = [0xef, 0x40, 0x18]
flash0.sector_size = 0x10000
flash0.sector_number = flash_image0.size // 0x10000
simics.SIM_add_configuration([flash_image0, flash0], None)
flash0 = conf.flash0
flash_image0 = conf.flash_image0
flash0.log_level = 4

master = du.Dev([["spi_master", dummy_spi_master]])
spif = flash0.iface.serial_peripheral_interface_slave

def command8(cmd):
    cmd = ((cmd&0xAA)>>1)|((cmd&0x55)<<1)
    cmd = ((cmd&0xCC)>>2)|((cmd&0x33)<<2)
    cmd = ((cmd&0xF0)>>4)|((cmd&0x0F)<<4)
    spif.connect_master(master.obj, "spi_master", 0)
    spif.spi_request(
        1, 1, 32,
        b''.join([bytes((cmd,)), b'\0', b'\0', b'\0']))
    spif.disconnect_master(master.obj)

command8(0x06)
