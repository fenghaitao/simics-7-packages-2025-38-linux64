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


# Try to add a new flash model and then instantiate it. The "new" flash is just
# a copy of S29GLxxxP

import flash_memory

SIM_source_python_in_module("common.py", __name__)

def finish_flash(product_no, config):
    # check size
    size = 1024

    config['unit_size'] = [128*1024]*size
    if size == 128:
        config["device_id"] = [0x227e, 0x2221, 0x2201]
        config["cfi_query"][0x27] = 0x18 # Device size
        config["cfi_query"][0x2d] = 0x7f # Erase block region 1 info
        config["cfi_query"][0x2e] = 0x00
    elif size == 256:
        config["device_id"] = [0x227e, 0x2222, 0x2201]
        config["cfi_query"][0x27] = 0x19
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x00
    elif size == 512:
        config["device_id"] = [0x227e, 0x2223, 0x2201]
        config["cfi_query"][0x27] = 0x1a
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x01
    else:
        config["device_id"] = [0x227e, 0x2228, 0x2201]
        config["cfi_query"][0x27] = 0x1b
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x03

    # not sure on this one, copy/paste..
    config["cfi_query"][0x4f] = 0x04  # bottom WP protect
    #config["cfi_query"][0x4f] = 0x05  # top WP protect

    return flash_memory.finish_default(product_no, config)

flash_memory.flash_add_model(
    "anewflash",
    {"cfi_query" : [0x04, 0x00, 0x00, 0x00, # 0x00
                    0x00, 0x00, 0x00, 0x00, # 0x04
                    0x00, 0x00, 0x00, 0x00, # 0x08
                    0x00, 0x00, 0x00, 0x00, # 0x0C
                    0x51, 0x52, 0x59, 0x02, # 0x10
                    0x00, 0x40, 0x00, 0x00, # 0x14
                    0x00, 0x00, 0x00, 0x27, # 0x18
                    0x36, 0x00, 0x00, 0x06, # 0x1C
                    0x06, 0x09, 0x13, 0x03, # 0x20
                    0x05, 0x03, 0x02, None, # 0x24
                    0x02, 0x00, 0x06, 0x00, # 0x28
                    0x01, None, None, 0x00, # 0x2C
                    0x02, 0x00, 0x00, 0x00, # 0x30
                    0x00, 0x00, 0x00, 0x00, # 0x34
                    0x00, 0x00, 0x00, 0x00, # 0x38
                    0x00, 0x00, 0x00, 0x00, # 0x3C
                    0x50, 0x52, 0x49, 0x31, # 0x40
                    0x33, 0x14, 0x02, 0x01, # 0x44
                    0x00, 0x08, 0x00, 0x00, # 0x48
                    0x02, 0xB5, 0xC5, None, # 0x4C
                    0x01], # 0x50
     "device_id" : None,
     "manufacturer_id" : 0x01,
     "max_chip_width" : 16,          # 16-bits chip
     },
    finish_flash)

make_flash_configuration('anewflash', 1, 16, "flash")

run_command('list-objects')
