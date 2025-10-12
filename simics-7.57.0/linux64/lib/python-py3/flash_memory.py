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


import copy
from comp import pre_obj
import cli

__all__ = ["flash_add_model", "flash_create_memory", "flash_create_memory_anon"]

# Have the cli classes and functions marked up as 'python flashmemory'
# in the reference documentation, rather than the default 'simics api
# python'.
__simicsapi_doc_id__ = 'python flashmemory'

# This is the generic flash-memory support provided by Simics
# For Serial Flash memory, please refer to device/generic-spi-flash
# The following flash memories are pre-configured:
# * Intel® 28FxxxC3x   (Advanced+ Boot Block Flash Memory)
# * Intel® 28FxxxJ3    (StrataFlash®)
# * Intel® 28FxxxJ3A   (StrataFlash®)
# * Intel® 28FxxxP30x  (StrataFlash®)
# * Intel® 28FxxxL18x  (StrataFlash®)
# * Intel® 28F160S3
# * Intel® 28F320S3
# * Am29F040B
# * Am29F016D
# * Am29SL160CT
# * Am29LV64xD  (and all L/H versions)
# * Am29LV640MH
# * Am29LV800BB
# * Am29LV800BT
# * Am29LV160MB
# * SG29GL064M
# * Am29DL323B
# * Am29DL323G_
# * Am29LV033C
# * MBM29LV650UE
# * Amd S29GLxxxN
# * AT49BV001A
# * S29GLxxxMr
# * S29GLxxxP
# * S29GL064A
# * S29AL016D-1
# * S29AL016D-2
# * S29AL008J-1
# * S29AL008J-2
# * S29AL004D-1
# * S29AL004D-2
# * SST39VF040
# * MX29GL256Ex
# * Micron xx28FxxxM29EWxx

# To add other flash configuration, edit the flash_description table to fill in
# the correct values for the flash you want to simulate. Add also a finish
# function that will parse the product name to complete the information. You
# can use the default function if no more configuration is needed.

# You can then use the add_flash_memory() function to add a flash memory in a
# standard python-based Simics configuration, or use the flash_create_memory()
# function that will simply return a list of objects to add to your own
# configuration

# The following commands are supported for Intel® flash memories:
# - CFI support (if any)
# - read identifier mode (including block locking status)
# - read/clear status register
# - write buffer
# - word program
# - block erase
# - simple locking scheme (strataflash) / advanced locking scheme

# The following commands are supported for AMD flash:
# - CFI support (if any)
# - autoselect mode (including protect verify)
# - program
# - sector erase
# - unlock bypass/program/reset (not tested properly)

########################################################
# EDIT TO ADD A NEW FLASH TYPE --- Flash Configuration #
########################################################

#
# Default completion function
#
# finish(product_no, config) -> (config_updated, size of one flash chip in bytes)
def finish_default(product_no, config):
    size = sum(config["unit_size"]) # compute total size
    return (config, size)

#
# Completion function for:
# Intel® 28F800C3T
#          160  B
#          320
#          640
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_28F___C3_(product_no, config):
    # set size-dependent parameters
    if   product_no[3:6] == "800":      # 8Mbit, Bottom
        device_geometry_definition = [0x14, 0x01, 0x00, 0x00, 0x00, 0x02, 0x07, 0x00, 0x20, 0x00, 0x0E, 0x00, 0x00, 0x01]
        device_id = 0x88C1
        big_blocks = 15
    elif product_no[3:6] == "160":      # 16Mbit, Bottom
        device_geometry_definition = [0x15, 0x01, 0x00, 0x00, 0x00, 0x02, 0x07, 0x00, 0x20, 0x00, 0x1E, 0x00, 0x00, 0x01]
        device_id = 0x88C3
        big_blocks = 31
    elif product_no[3:6] == "320":      # 32Mbit, Bottom
        device_geometry_definition = [0x16, 0x01, 0x00, 0x00, 0x00, 0x02, 0x07, 0x00, 0x20, 0x00, 0x3E, 0x00, 0x00, 0x01]
        device_id = 0x88C5
        big_blocks = 63
    elif product_no[3:6] == "640":      # 64Mbit, Bottom
        device_geometry_definition = [0x17, 0x01, 0x00, 0x00, 0x00, 0x02, 0x07, 0x00, 0x20, 0x00, 0x7E, 0x00, 0x00, 0x01]
        device_id = 0x88CD
        big_blocks = 127
    else:
        return "The product no (" + product_no + ") should contain a valid size (800, 160, 320 or 640), not '" + product_no[3:6] + "'"

    # size
    size = 1 << device_geometry_definition[0]

    # check what where the boot block is
    if   product_no[8] == "T":
        boot_block = "top"
    elif product_no[8] == "B":
        boot_block = "bottom"
    else:
        return "The product no (" + product_no + ") should end with T (for top) or B (for bottom), not '" + product_no[8] + "'"

    # cfi_query
    for i in range(0x27, 0x2D):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    if boot_block == "bottom":
        # bottom blocking is already configured
        for i in range(0x2D, 0x35):
            config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    else:
        # top blocking is inverted
        for i in range(0x2D, 0x31):
            config["cfi_query"][i] = device_geometry_definition[i - 0x27 + 4]
        for i in range(0x31, 0x35):
            config["cfi_query"][i] = device_geometry_definition[i - 0x27 - 4]

    # device-id
    if boot_block == "top":
        config['device_id'] = device_id - 1
    else:
        config['device_id'] = device_id

    # unit_size
    if boot_block == "top":
        config['unit_size'] = [0x10000 for i in range(big_blocks)] + [0x2000 for i in range(8)]
    else:
        config['unit_size'] = [0x2000 for i in range(8)] +  [0x10000 for i in range(big_blocks)]
    return (config, size)

#
# Completion function for:
# Intel® 28F160S3
#          320
#
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_28F___S3 (product_no, config):
    # set size-dependent parameters
    if   product_no[3:6] == "160":       # 16Mbit
        device_geometry_definition = [0x15, 0x02, 0x00, 0x05, 0x00, 0x01, 0x1f, 0x00, 0x00, 0x01]
        config['device_id'] = 0xd0
        blocks = 32
    elif product_no[3:6] == "320":       # 32Mbit
        device_geometry_definition = [0x16, 0x02, 0x00, 0x05, 0x00, 0x01, 0x3f, 0x00, 0x00, 0x01]
        config['device_id'] = 0xd4
        blocks = 64
    else:
        return "The product no (" + product_no + ") should contain a valid size (160 or 320), not '" + product_no[3:6] + "'"

    # size
    size = 1 << device_geometry_definition[0]

    # cfi_query
    for i in range(0x27, 0x31):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    config['unit_size'] = [0x10000 for i in range(blocks)]
    return (config, size)

#
# Completion function for:
# Intel® 28F320J3A
#          640
#          128
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_28F___J3A(product_no, config):
    # set size-dependent parameters
    if   product_no[3:6] == "320":      # 32Mbit
        device_geometry_definition = [0x16, 0x02, 0x00, 0x05, 0x00, 0x01, 0x1F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0016
        blocks = 32
    elif product_no[3:6] == "640":      # 64Mbit
        device_geometry_definition = [0x17, 0x02, 0x00, 0x05, 0x00, 0x01, 0x3F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0017
        blocks = 64
    elif product_no[3:6] == "128":      # 128Mbit
        device_geometry_definition = [0x18, 0x02, 0x00, 0x05, 0x00, 0x01, 0x7F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0018
        blocks = 128
    else:
        return "The product no (" + product_no + ") should contain a valid size (320, 640 or 128), not '" + product_no[3:6] + "'"

    # size
    size = 1 << device_geometry_definition[0]

    # cfi_query
    for i in range(0x27, 0x31):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    config['unit_size'] = [0x20000 for i in range(blocks)]
    return (config, size)

#
# Completion function for:
# Intel® 28F320J3
#          640
#          128
#          256
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_28F___J3(product_no, config):
    # set size-dependent parameters
    if product_no[3:6] == "320":      # 32Mbit
        device_geometry_definition = [0x16, 0x02, 0x00, 0x05, 0x00, 0x01, 0x1F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0016
        blocks = 32
    elif product_no[3:6] == "640":      # 64Mbit
        device_geometry_definition = [0x17, 0x02, 0x00, 0x05, 0x00, 0x01, 0x3F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0017
        blocks = 64
    elif product_no[3:6] == "128":      # 128Mbit
        device_geometry_definition = [0x18, 0x02, 0x00, 0x05, 0x00, 0x01, 0x7F, 0x00, 0x00, 0x02]
        config['device_id'] = 0x0018
        blocks = 128
    elif product_no[3:6] == "256":      # 256Mbit
        device_geometry_definition = [0x19, 0x02, 0x00, 0x05, 0x00, 0x01, 0xFF, 0x00, 0x00, 0x02]
        config['device_id'] = 0x001D
        blocks = 256
    else:
        return "The product no (" + product_no + ") should contain a valid size (320, 640, 128 or 256), not '" + product_no[3:6] + "'"

    # size
    size = 1 << device_geometry_definition[0]

    # cfi_query
    for i in range(0x27, 0x31):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    config['unit_size'] = [0x20000 for i in range(blocks)]
    return (config, size)

# Completion function for:
# Intel StrataFlash® Embedded Memory (P30)
#
def finish_config_28F___P30_(product_no, config):
    # Add Intel specific extended query data
    config['cfi_query'] += [0x00] * (0x10a - len(config['cfi_query']))
    config['cfi_query'] += [0x50, 0x52,              # 0x10a
                            0x49, 0x31, 0x34, 0xe6,  # 0x10c
                            0x01, 0x00, 0x00, 0x01,  # 0x110
                            0x03, 0x00, 0x18, 0x90,  # 0x114
                            0x02, 0x80, 0x00, 0x03,  # 0x118
                            0x03, 0x89, 0x00, 0x00,  # 0x11c
                            0x00, 0x00, 0x00, 0x00,  # 0x120
                            0x10, 0x00, 0x04, 0x03,  # 0x124
                            0x04, 0x01, 0x02, 0x03,  # 0x128
                            0x07, 0x01, 0x24, 0x00,  # 0x12c
                            0x01, 0x00, 0x11, 0x00,  # 0x130
                            0x00, 0x02, None, None,  # 0x134
                            None, None, 0x64, 0x00,  # 0x138
                            0x02, 0x03, 0x00, 0x80,  # 0x13c
                            0x00, 0x00, 0x00, 0x80,  # 0x140
                            None, None, None, None,  # 0x144
                            0x64, 0x00, 0x02, 0x03,  # 0x148
                            0x00, 0x80, 0x00, 0x00,  # 0x14c
                            0x00, 0x80, 0xff, 0xff,  # 0x150
                            0xff, 0xff, 0xff]        # 0x154

    # Where is the boot block?
    if product_no[-1] == "T":
        boot_block = "top"
    elif product_no[-1] == "B":
        boot_block = "bottom"
    else:
        return ("The product no (" + product_no + ") should end with TQ0/T00 "
                "(for top) or BQ0/B00 (for bottom), not '"
                + product_no[-3] + "'")

    # Chip size?
    if product_no[3:6] == "640":       # 64 Mbit
        blocks = 64
        config['device_id'] = 0x881a if boot_block == "bottom" else 0x8817

        device_geometry = [0x17, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0x3e, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0x3e, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

        if boot_block == "bottom":
            config['cfi_query'][0x136:0x13a] = [0x03, 0x00, 0x80, 0x00]
            config['cfi_query'][0x144:0x148] = [0x3e, 0x00, 0x00, 0x02]
        else:
            config['cfi_query'][0x136:0x13a] = [0x3e, 0x00, 0x00, 0x02]
            config['cfi_query'][0x144:0x148] = [0x03, 0x00, 0x80, 0x00]

    elif product_no[3:6] == "128":     # 128 Mbit
        blocks = 128
        config['device_id'] = 0x881b if boot_block == "bottom" else 0x8818

        device_geometry = [0x18, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0x7e, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0x7e, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

        if boot_block == "bottom":
            config['cfi_query'][0x136:0x13a] = [0x03, 0x00, 0x80, 0x00]
            config['cfi_query'][0x144:0x148] = [0x7e, 0x00, 0x00, 0x02]
        else:
            config['cfi_query'][0x136:0x13a] = [0x7e, 0x00, 0x00, 0x02]
            config['cfi_query'][0x144:0x148] = [0x03, 0x00, 0x80, 0x00]

    elif product_no[3:6] == "256":     # 256 Mbit
        blocks = 256
        config['device_id'] = 0x891c if boot_block == "bottom" else 0x8919

        device_geometry = [0x19, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0xfe, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0xfe, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

        if boot_block == "bottom":
            config['cfi_query'][0x136:0x13a] = [0x03, 0x00, 0x00, 0x80]
            config['cfi_query'][0x144:0x148] = [0xfe, 0x00, 0x00, 0x02]
        else:
            config['cfi_query'][0x136:0x13a] = [0xfe, 0x00, 0x00, 0x02]
            config['cfi_query'][0x144:0x148] = [0x03, 0x00, 0x00, 0x80]
    else:
        return ("The product no (" + product_no + ") should contain a valid "
                "size specification (640/128/256), not '"
                + product_no[3:6] + "'")

    size = 1 << device_geometry[0]
    for i in range(0x27, 0x39):
        config['cfi_query'][i] = device_geometry[i - 0x27]

    if boot_block == "top":
        config['unit_size'] = [0x20000] * (blocks - 1) + [0x8000] * 4
    else:
        config['unit_size'] = [0x8000] * 4 + [0x20000] * (blocks - 1)
    return (config, size)

# Completion function for:
# Intel StrataFlash® Wireless Memory (L18)
#
def finish_config_28F___L18_(product_no, config):
    # Add Intel specific extended query data
    config['cfi_query'] += [0x00] * (0x10a - len(config['cfi_query']))
    config['cfi_query'] += [0x50, 0x52,              # 0x10a
                            0x49, 0x31, 0x33, 0xe6,  # 0x10c
                            0x03, 0x00, 0x00, 0x01,  # 0x110
                            0x03, 0x00, 0x18, 0x90,  # 0x114
                            0x02, 0x80, 0x00, 0x03,  # 0x118
                            0x03, 0x89, 0x00, 0x00,  # 0x11c
                            0x00, 0x00, 0x00, 0x00,  # 0x120
                            0x10, 0x00, 0x04, 0x03,  # 0x124
                            0x04, 0x01, 0x02, 0x03,  # 0x128
                            0x07]                    # 0x12c


    # Where is the boot block?
    if product_no[-1] == "T":
        boot_block = "top"
        partition_info  = [       0x01, 0x07, 0x00,  # 0x12c
                            0x11, 0x00, 0x00, 0x02,  # 0x130
                            0x07, 0x00, 0x00, 0x02,  # 0x134
                            0x64, 0x00, 0x02, 0x03,  # 0x138
                            0x01, 0x00, 0x11, 0x00,  # 0x13c
                            0x00, 0x02, 0x06, 0x00,  # 0x140
                            0x00, 0x02, 0x64, 0x00,  # 0x144
                            0x00, 0x03, 0x03, 0x00,  # 0x148
                            0x80, 0x00, 0x64, 0x00,  # 0x14c
                            0x02, 0x03]              # 0x150
    elif product_no[-1] == "B":
        boot_block = "bottom"
        partition_info  = [       0x01, 0x01, 0x00,  # 0x12c
                            0x11, 0x00, 0x01, 0x02,  # 0x130
                            0x03, 0x00, 0x08, 0x00,  # 0x134
                            0x64, 0x00, 0x02, 0x03,  # 0x138
                            0x06, 0x00, 0x00, 0x02,  # 0x13c
                            0x64, 0x00, 0x02, 0x03,  # 0x140
                            0x07, 0x00, 0x11, 0x00,  # 0x144
                            0x00, 0x01, 0x07, 0x00,  # 0x148
                            0x00, 0x02, 0x64, 0x00,  # 0x14c
                            0x02, 0x03]              # 0x150
    else:
        return ("The product no (" + product_no + ") should end with L18T "
                "(for top) or L18B (for bottom), not '"
                + product_no[-4] + "'")

    config['cfi_query'] += partition_info

    # Chip size?
    if product_no[3:6] == "640":       # 64 Mbit
        blocks = 64
        config['device_id'] = 0x880e if boot_block == "bottom" else 0x880b

        device_geometry = [0x17, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0x3e, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0x3e, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

    elif product_no[3:6] == "128":     # 128 Mbit
        blocks = 128
        config['device_id'] = 0x880f if boot_block == "bottom" else 0x880c

        device_geometry = [0x18, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0x7e, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0x7e, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

        if boot_block == "bottom":
            config['cfi_query'][0x144] = 0x0f
        else:
            config['cfi_query'][0x12e] = 0x0f

    elif product_no[3:6] == "256":     # 256 Mbit
        blocks = 256
        config['device_id'] = 0x8810 if boot_block == "bottom" else 0x880d

        device_geometry = [0x19, 0x01, 0x00, 0x06, 0x00, 0x02]
        if boot_block == "bottom":
            device_geometry += [0x03, 0x00, 0x80, 0x00, 0xfe, 0x00, 0x00, 0x02]
        else:
            device_geometry += [0xfe, 0x00, 0x00, 0x02, 0x03, 0x00, 0x80, 0x00]
        device_geometry += [0x00, 0x00, 0x00, 0x00]

        if boot_block == "bottom":
            config['cfi_query'][0x13c] = 0x0e
            config['cfi_query'][0x144] = 0x0f
            config['cfi_query'][0x14a] = 0x0f
        else:
            config['cfi_query'][0x12e] = 0x0f
            config['cfi_query'][0x142] = 0x0e
            config['cfi_query'][0x134] = 0x0f
    else:
        return ("The product no (" + product_no + ") should contain a valid "
                "size specification (640/128/256), not '"
                + product_no[3:6] + "'")

    size = 1 << device_geometry[0]
    for i in range(0x27, 0x39):
        config['cfi_query'][i] = device_geometry[i - 0x27]

    if boot_block == "top":
        config['unit_size'] = [0x20000] * (blocks - 1) + [0x8000] * 4
    else:
        config['unit_size'] = [0x8000] * 4 + [0x20000] * (blocks - 1)
    return (config, size)

#
# Completion function for:
# Numonyx* 28F256M29EW[HL]
#             512
#             00a
#             00b
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_28F___M29EW_(product_no, config):
    # set size-dependent parameters
    if product_no[3:6] == "256":      # 256Mbit
        device_geometry_definition = [0x19, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x00, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x12
        config['device_id'] = 0x2222
        blocks = 256
    elif product_no[3:6] == "512":      # 512Mbit
        device_geometry_definition = [0x1a, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x01, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x13
        config['device_id'] = 0x2223
        blocks = 512
    elif product_no[3:6] == "00a":      # 1Gbit
        device_geometry_definition = [0x1b, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x03, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x14
        config['device_id'] = 0x2228
        blocks = 1024
    elif product_no[3:6] == "00b":      # 2Gbit
        device_geometry_definition = [0x1c, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x07, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x15
        config['device_id'] = 0x2248
        blocks = 2048
    else:
        return "The product no (" + product_no + ") should contain a valid size (256, 512, 00a or 00b), not '" + product_no[3:6] + "'"

    # boot block protection flag
    if product_no[-1] == "L":
        config['cfi_query'][0x4f] = 0x04
    elif product_no[-1] == "H":
        config['cfi_query'][0x4f] = 0x05
    else:
        return ("The product no (" + product_no + ") should end with M29EWH "
                "(for top/high) or M29EWL (for bottom/low), not '"
                + product_no[-6] + "'")

    # size
    size = 1 << device_geometry_definition[0]

    # cfi_query
    for i in range(0x27, 0x31):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    config['unit_size'] = [0x20000 for i in range(blocks)]
    return (config, size)


#
# Completion function for:
# Am29BDS128
# Am29BDS640
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_Am29BDS___(product_no, config):
    # check what where the boot block is
    if   product_no.endswith("128"):
        config['unit_size'] = [0x2000 for i in range(8)] + [0x10000 for i in range(254)] + [0x2000 for i in range(8)]
        config["cfi_query"][0x27] = 0x18
        config["cfi_query"][0x31] = 0xFD
        config["cfi_query"][0x4A] = 0xE7
        config["cfi_query"][0x58] = 0x27
        config["cfi_query"][0x59] = 0x60
        config["cfi_query"][0x5A] = 0x60
        config["cfi_query"][0x5B] = 0x27
        config['device_id'] = [0x227E, 0x2218, 0x2200]
    elif product_no.endswith("640"):
        config['unit_size'] = [0x2000 for i in range(8)] + [0x10000 for i in range(126)] + [0x2000 for i in range(8)]
        config["cfi_query"][0x27] = 0x17
        config["cfi_query"][0x31] = 0x7D
        config["cfi_query"][0x4A] = 0x77
        config["cfi_query"][0x58] = 0x17
        config["cfi_query"][0x59] = 0x30
        config["cfi_query"][0x5A] = 0x30
        config["cfi_query"][0x5B] = 0x17
        config['device_id'] = [0x227E, 0x221E, 0x2201]
    else:
        return "The product no (" + product_no + ") must end with 128 or 640"

    return finish_default(product_no, config)

#
# Completion function for:
# Am29DL323GB
# Am29DL323GT
#
# finish(product_no, config) -> (config_updated, size of one flash chip, in bytes)
def finish_config_Am29DL323G_(product_no, config):
    # check what where the boot block is
    if   product_no[-1] == "T":
        boot_block = "top"
    elif product_no[-1] == "B":
        boot_block = "bottom"
    else:
        return "The product no (" + product_no + ") should end with T (for top) or B (for bottom), not '" + product_no[-1] + "'"

    if boot_block == "top":
        config['device_id'] = 0x2250
        config['unit_size'] = [0x10000]*63 + [0x2000]*8
        config["cfi_query"][0x4f] = 0x03
    else:
        config['device_id'] = 0x2253
        config['unit_size'] = [0x2000]*8 + [0x10000]*63
        config["cfi_query"][0x4f] = 0x02

    return finish_default(product_no, config)

#
# Completion function for:
# S29GL032Mr   r=range(7)
# S29GL064Mr   r=range(10)
# S29GL128Mr   r=[1,2,8,9]
# S29GL256Mr   r=[1,2]
#
def finish_config_S29GL___M_(product_no, config):
    # check size
    if product_no[5:8] == "032":
        if product_no[9] == "0":
            config["device_id"] = [0x227e, 0x221c, 0x2200]
        elif product_no[9] in "12":
            config["device_id"] = [0x227e, 0x221d, 0x2200]
        elif product_no[9] in "35":
            config["device_id"] = [0x227e, 0x221a, 0x2200]
        elif product_no[9] in "46":
            config["device_id"] = [0x227e, 0x221a, 0x2201]
        else:
            config["device_id"] = [0x227e, 0x221c, 0x2200]
        config["cfi_query"][0x27] = 0x16
        if product_no[9] == "0":
            config["cfi_query"][0x28] = 0x00
        else:
            config["cfi_query"][0x28] = 0x02
        if product_no[9] in "3456":
            config["cfi_query"][0x2c] = 0x02
        else:
            config["cfi_query"][0x2c] = 0x01
        config["cfi_query"][0x2e] = 0x00
        if product_no[9] in "12":
            config["cfi_query"][0x2d] = 0x3f
            config["cfi_query"][0x2f] = 0x00
            config["cfi_query"][0x30] = 0x01
            config["cfi_query"][0x31] = 0x00
            config["cfi_query"][0x34] = 0x00
        else:
            config["cfi_query"][0x2d] = 0x7f
            config["cfi_query"][0x2f] = 0x20
            config["cfi_query"][0x30] = 0x00
            config["cfi_query"][0x31] = 0x3e
            config["cfi_query"][0x34] = 0x01
        if product_no[9] == "0":
            config["cfi_query"][0x45] = 0x09
            config["max_chip_width"] = 8
        else:
            config["cfi_query"][0x45] = 0x08
            config["max_chip_width"] = 16
        if product_no[9] == "0":
            config["cfi_query"][0x4f] = 0x00
        elif product_no[9] == "1":
            config["cfi_query"][0x4f] = 0x05
        elif product_no[9] == "2":
            config["cfi_query"][0x4f] = 0x04
        elif product_no[9] in "35":
            config["cfi_query"][0x4f] = 0x03
        elif product_no[9] in "46":
            config["cfi_query"][0x4f] = 0x02
        else:
            config["cfi_query"][0x4f] = 0x00
        (sector_size, sector_count) = (64, 64)
    elif product_no[5:8] == "064":
        if product_no[9] == "0":
            config["device_id"] = [0x227e, 0x2213, 0x2200]
        elif product_no[9] in "12":
            config["device_id"] = [0x227e, 0x220c, 0x2201]
        elif product_no[9] == "3":
            config["device_id"] = [0x227e, 0x2210, 0x2200]
        elif product_no[9] == "4":
            config["device_id"] = [0x227e, 0x2210, 0x2201]
        elif product_no[9] in "56":
            config["device_id"] = [0x227e, 0x2213, 0x2201]
        else:
            config["device_id"] = [0x227e, 0x2213, 0x2200]
        config["cfi_query"][0x27] = 0x17
        if product_no[9] == "0":
            config["cfi_query"][0x28] = 0x00
        elif product_no[9] in "567":
            config["cfi_query"][0x28] = 0x01
        else:
            config["cfi_query"][0x28] = 0x02
        if product_no[9] in "34":
            config["cfi_query"][0x2c] = 0x02
        else:
            config["cfi_query"][0x2c] = 0x01
        config["cfi_query"][0x2e] = 0x00
        if product_no[9] in "12":
            config["cfi_query"][0x2d] = 0x7f
            config["cfi_query"][0x2f] = 0x00
            config["cfi_query"][0x30] = 0x01
            config["cfi_query"][0x31] = 0x00
            config["cfi_query"][0x34] = 0x00
        else:
            config["cfi_query"][0x2d] = 0x7f
            config["cfi_query"][0x2f] = 0x20
            config["cfi_query"][0x30] = 0x00
            config["cfi_query"][0x31] = 0x7e
            config["cfi_query"][0x34] = 0x01
        if product_no[9] == "0":
            config["cfi_query"][0x45] = 0x09
            config["max_chip_width"] = 8
        else:
            config["cfi_query"][0x45] = 0x08
            config["max_chip_width"] = 16
        if product_no[9] == "0":
            config["cfi_query"][0x4f] = 0x00
        elif product_no[9] in "168":
            config["cfi_query"][0x4f] = 0x05
        elif product_no[9] in "279":
            config["cfi_query"][0x4f] = 0x04
        elif product_no[9] == "3":
            config["cfi_query"][0x4f] = 0x03
        elif product_no[9] == "4":
            config["cfi_query"][0x4f] = 0x02
        else:
            config["cfi_query"][0x4f] = 0x00
        (sector_size, sector_count) = (64, 128)
    elif product_no[5:8] == "128":
        config["device_id"] = [0x227e, 0x2212, 0x2200]
        config["cfi_query"][0x27] = 0x18
        config["cfi_query"][0x28] = 0x02
        config["cfi_query"][0x2c] = 0x01
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x00
        config["cfi_query"][0x2f] = 0x00
        config["cfi_query"][0x30] = 0x01
        config["cfi_query"][0x31] = 0x00
        config["cfi_query"][0x34] = 0x00
        config["cfi_query"][0x45] = 0x08
        config["max_chip_width"] = 16
        if product_no[9] in "18":
            config["cfi_query"][0x4f] = 0x05
        elif product_no[9] in "29":
            config["cfi_query"][0x4f] = 0x04
        else:
            config["cfi_query"][0x4f] = 0x00
        (sector_size, sector_count) = (64, 256)
    elif product_no[5:8] == "256":
        config["device_id"] = [0x227e, 0x2212, 0x2201]
        config["cfi_query"][0x27] = 0x19
        config["cfi_query"][0x28] = 0x02
        config["cfi_query"][0x2c] = 0x01
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x01
        config["cfi_query"][0x2f] = 0x00
        config["cfi_query"][0x30] = 0x01
        config["cfi_query"][0x31] = 0x00
        config["cfi_query"][0x34] = 0x00
        config["cfi_query"][0x45] = 0x08
        config["max_chip_width"] = 16
        if product_no[9] == "1":
            config["cfi_query"][0x4f] = 0x05
        elif product_no[9] == "2":
            config["cfi_query"][0x4f] = 0x04
        else:
            config["cfi_query"][0x4f] = 0x00
        (sector_size, sector_count) = (64, 512)
    else:
        return "The product no (" + product_no + ") is not supported. Only 32,64,128 or 256 Mbit are supported."

    config["unit_size"] = [sector_size * 1024] * sector_count

    return finish_default(product_no, config)

#
# Completion function for:
# S29GL064N
# S29GL128N
# S29GL256N
# S29GL512N
#
def finish_config_S29GL___N(product_no, config):
    # check size
    if   product_no[5:8] == "064":
        config["device_id"] = [0x227e, 0x2220, 0x2201]
        config["cfi_query"][0x27] = 0x17
        config["cfi_query"][0x2d] = 0x7f
        config["cfi_query"][0x2e] = 0x00
        (sector_size, sector_count) = (64, 128)
    elif product_no[5:8] == "128":
        config["device_id"] = [0x227e, 0x2221, 0x2201]
        config["cfi_query"][0x27] = 0x18
        config["cfi_query"][0x2d] = 0x7f
        config["cfi_query"][0x2e] = 0x00
        (sector_size, sector_count) = (128, 128)
    elif product_no[5:8] == "256":
        config["device_id"] = [0x227e, 0x2222, 0x2201]
        config["cfi_query"][0x27] = 0x19
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x00
        (sector_size, sector_count) = (128, 256)
    elif product_no[5:8] == "512":
        config["device_id"] = [0x227e, 0x2223, 0x2201]
        config["cfi_query"][0x27] = 0x1a
        config["cfi_query"][0x2d] = 0xff
        config["cfi_query"][0x2e] = 0x01
        (sector_size, sector_count) = (128, 512)
    else:
        return "The product no (" + product_no + ") is not supported. Only 64,128,256 or 512 Mbit are supported."

    config["unit_size"] = [sector_size * 1024] * sector_count

    # not sure on this one
    config["cfi_query"][0x4f] = 0x04  # bottom WP protect
    #config["cfi_query"][0x4f] = 0x05  # top WP protect

    return finish_default(product_no, config)

#
# Completion function for:
# S29GL01GP
# S29GL512P
# S29GL256P
# S29GL128P
#
def finish_config_S29GL___P(product_no, config):
    # check size
    if   product_no[5:8] == "128":
        size = 128
    elif product_no[5:8] == "256":
        size = 256
    elif product_no[5:8] == "512":
        size = 512
    elif product_no[5:8] == "01G":
        size = 1024
    else:
        return "The product no (" + product_no + ") is not supported. Only 128,256, 512 or 1024 Mbit are supported."

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

    return finish_default(product_no, config)

#
# Completion function for:
# Macronix MX29GL256E[HLUD]
#
# when trying to add a new configuration of Macronix flash,
# please try to modify this completion function
# first instead of adding a new configuration if possible,
# substitute '_' for corresponding characters in the name, and
# add new configuration in this function
def finish_config_MX29GL256E_(product_no, config):
    # boot block protection flag
    if product_no[-1] == "L" or product_no[-1] == "D":
        config['cfi_query'][0x4f] = 0x04
    elif product_no[-1] == "H" or product_no[-1] == "U":
        config['cfi_query'][0x4f] = 0x05
    else:
        return ("The product no (" + product_no + ") should end with H/U "
                "(for top/high) or L/D (for bottom/low), not '"
                + product_no[-1] + "'")

    return finish_default(product_no, config)

#
# Completion function for:
# Micron __28F___M29EW__
#       JS    256     HA
#       PC    512     LB
#       RC    00A      D
#             00B      E
#                      *
def finish_config___28F___M29EW__(product_no, config):
    if product_no[0:2] not in ["JS", "PC", "RC"]:
        return ("The product no (" + product_no + ") should begin with one of "
                "JS/PC/RC, not '"+ product_no[0:2] + "'")

    # set size-dependent parameters
    if product_no[5:8] == "256":      # 256Mbit
        device_geometry_definition = [0x19, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x00, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x12
        config['device_id'] = [0x227e, 0x2222, 0x2201]
        blocks = 256
    elif product_no[5:8] == "512":      # 512Mbit
        device_geometry_definition = [0x1a, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x01, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x13
        config['device_id'] = [0x227e, 0x2223, 0x2201]
        blocks = 512
    elif product_no[5:8] == "00A":      # 1Gbit
        device_geometry_definition = [0x1b, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x03, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x14
        config['device_id'] = [0x227e, 0x2228, 0x2201]
        blocks = 1024
    elif product_no[5:8] == "00B":      # 2Gbit
        device_geometry_definition = [0x1c, 0x02, 0x00, 0x0a, 0x00, 0x01, 0xff, 0x07, 0x00, 0x02]
        config['cfi_query'][0x22] = 0x15
        config['device_id'] = [0x227e, 0x2248, 0x2201]
        blocks = 2048
    else:
        return ("The product no (" + product_no + ") should contain a valid size (256, 512, 00A or 00B),"
               " not '" + product_no[5:8] + "'")

    # boot block protection flag
    if product_no[-2] == "L":
        config['cfi_query'][0x4f] = 0x04
    elif product_no[-2] == "H":
        config['cfi_query'][0x4f] = 0x05
    else:
        return ("The product no (" + product_no + ") should end with H_ "
                "(for top/high) or L_ (for bottom/low), not '"
                + product_no[-2] + "'")

    if product_no[-1] not in ["A", "B", "D", "E", "*"]:
        return ("The product no (" + product_no + ") should end with one of "
                "A/B/D/E/*, not '"+ product_no[-1] + "'")

    # cfi_query: Device geometry definition
    for i in range(0x27, 0x31):
        config["cfi_query"][i] = device_geometry_definition[i - 0x27]
    config['unit_size'] = [0x20000 for i in range(blocks)]
    return finish_default(product_no, config)

#
# list of completion functions
#
complete_functions = {
    "28F___C3_": finish_config_28F___C3_,
    "28F___J3A": finish_config_28F___J3A,
    "28F___J3": finish_config_28F___J3,
    "28F___S3": finish_config_28F___S3,
    "28F___P30_": finish_config_28F___P30_,
    "28F___L18_": finish_config_28F___L18_,
    "28F___M29EW_": finish_config_28F___M29EW_,
    "82802-8": finish_default,
    "Am29F040B": finish_default,
    "Am29F016D": finish_default,
    "Am29SL160CT": finish_default,
    "Am29LV640MH": finish_default,
    "Am29LV64_D": finish_default,
    "Am29LV800BB": finish_default,
    "Am29LV800BT": finish_default,
    "Am29LV160MB": finish_default,
    "SG29GL064M": finish_default,
    "Am29DL323B": finish_default,
    "Am29DL323G_": finish_config_Am29DL323G_,
    "Am29LV033C": finish_default,
    "MBM29LV650UE": finish_default,
    "S29GL___M_": finish_config_S29GL___M_,
    "S29GL___N": finish_config_S29GL___N,
    "S29GL___P": finish_config_S29GL___P,
    "S29GL064A": finish_default,
    "AT49BV001A": finish_default,
    "AT49BV001AT": finish_default,
    "Am29BDS___": finish_config_Am29BDS___,
    "S29AL016D-1": finish_default,
    "S29AL016D-2": finish_default,
    "S29AL008J-1": finish_default,
    "S29AL008J-2": finish_default,
    "S29AL004D-1": finish_default,
    "S29AL004D-2": finish_default,
    "SST39VF040": finish_default,
    "MX29GL256E_": finish_config_MX29GL256E_,
    "__28F___M29EW__": finish_config___28F___M29EW__,
    }

#
# static description of flash memory chips
#
flash_descriptions = {
    "28F___C3_": {
        "cfi_query" : [0x89, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x03, # 0x10
                       0x00, 0x35, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0xB4, 0xC6, 0x05, # 0x1C
                       0x00, 0x0A, 0x00, 0x04, # 0x20
                       0x00, 0x03, 0x00, None, # 0x24
                       None, None, None, None, # 0x28
                       None, None, None, None, # 0x2C
                       None, None, None, None, # 0x30
                       None,                   # 0x34
                       0x50, 0x52, 0x49, 0x31, # 0x35 Extended Query
                       0x30, 0x66, 0x00, 0x00, # 0x39
                       0x00, 0x01, 0x03, 0x00, # 0x3D
                       0x33, 0xC0, 0x01, 0x80, # 0x41
                       0x00, 0x03, 0x03],      # 0x45
        "device_id" : None,
        "manufacturer_id" : 0x0089,     # Intel
        "max_chip_width" : 16,          # 16-bits chips
        "unit_size" : None,
        "intel_write_buffer" : 0,       # no write-buffer in C3
        "intel_protection_program" : 1,
        "intel_configuration" : 1,
        "intel_lock" : 2                # advanced locking
        },

    "28F___P30_": {
        "cfi_query" : [0x89, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0c
                       0x51, 0x52, 0x59, 0x01, # 0x10
                       0x00, 0x0a, 0x01, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x17, # 0x18
                       0x20, 0x85, 0x95, 0x08, # 0x1c
                       0x09, 0x0a, 0x00, 0x01, # 0x20
                       0x01, 0x02, 0x00, None, # 0x24
                       0x01, 0x00, 0x06, 0x00, # 0x28
                       # Device geometry - filled in by complete function
                       None, None, None, None, # 0x2c
                       None, None, None, None, # 0x30
                       None, None, None, None, # 0x34
                       None],
        "device_id" : None,
        "manufacturer_id" : 0x0089,            # Intel
        "max_chip_width" : 16,
        "unit_size" : None,
        "write_buffer_size" : 64,

        # TODO: verify these
        "intel_write_buffer" : 1,
        "intel_protection_program" : 1,
        "intel_configuration" : 1,
        "intel_lock" : 2                       # Advanced locking
        },

    "28F___L18_": {
        "cfi_query" : [0x89, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0c
                       0x51, 0x52, 0x59, 0x01, # 0x10
                       0x00, 0x0a, 0x01, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x17, # 0x18
                       0x20, 0x85, 0x95, 0x08, # 0x1c
                       0x09, 0x0a, 0x00, 0x01, # 0x20
                       0x01, 0x02, 0x00, None, # 0x24
                       0x01, 0x00, 0x06, 0x00, # 0x28
                       # Device geometry - filled in by complete function
                       None, None, None, None, # 0x2c
                       None, None, None, None, # 0x30
                       None, None, None, None, # 0x34
                       None],
        "device_id" : None,
        "manufacturer_id" : 0x0089,            # Intel
        "max_chip_width" : 16,
        "unit_size" : None,

        # TODO: verify these
        "intel_write_buffer" : 1,
        "intel_protection_program" : 1,
        "intel_configuration" : 1,
        "intel_lock" : 2                       # Advanced locking
        },

    "28F___S3": {
         "cfi_query" : [0xb0, 0x00, 0x00, 0x00, # 0x00  Sharp Manufacturer ID
                        0x00, 0x00, 0x00, 0x00, # 0x04
                        0x00, 0x00, 0x00, 0x00, # 0x08
                        0x00, 0x00, 0x00, 0x00, # 0x0C
                        0x51, 0x52, 0x59, 0x01, # 0x10
                        0x00, 0x31, 0x00, 0x00, # 0x14 0x15 is Pointer to Extended Query
                        0x00, 0x00, 0x00, 0x27, # 0x18
                        0x55, 0x27, 0x55, 0x03, # 0x1C
                        0x06, 0x0A, 0x0f, 0x04, # 0x20
                        0x04, 0x04, 0x04, None, # 0x24
                        None, None, None, None, # 0x28
                        None, None, None, None, # 0x2C
                        None,
                        0x50, 0x52, 0x49, 0x31, # 0x31 Extended Query
                        0x30, 0x0f, 0x00, 0x00, # 0x35
                        0x00, 0x01, 0x03, 0x00, # 0x39
                        0x50, 0x50],            # 0x3D
         "device_id" : None,                    #
         "manufacturer_id" : 0x00b0,            # Sharp Manufacturer ID is verbatim from Intel docs.
         "max_chip_width" : 16,          # 16-bits chips
         "unit_size" : None,
         "intel_write_buffer" : 1,
         "intel_protection_program" : 0, # No protection command on S3
         "intel_configuration" : 1,
         "intel_lock" : 1                # Simple locking
         },

    "28F___J3A": {
        "cfi_query" : [0x89, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x01, # 0x10
                       0x00, 0x31, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0A, 0x00, 0x04, # 0x20
                       0x04, 0x04, 0x00, None, # 0x24
                       None, None, None, None, # 0x28
                       None, None, None, None, # 0x2C
                       None,
                       0x50, 0x52, 0x49, 0x31, # 0x31 Extended Query
                       0x31, 0x0A, 0x00, 0x00, # 0x35
                       0x00, 0x01, 0x01, 0x00, # 0x39
                       0x33, 0x00, 0x01, 0x00, # 0x3D
                       0x03, 0x00],            # 0x41
        "device_id" : None,
        "manufacturer_id" : 0x0089,     # Intel
        "max_chip_width" : 16,          # 16-bits chips
        "unit_size" : None,
        "intel_write_buffer" : 1,
        "intel_protection_program" : 1,
        "intel_configuration" : 1,
        "intel_lock" : 1                # simple locking
        },

    "28F___J3": {
        "cfi_query" : [0x89, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x01, # 0x10
                       0x00, 0x31, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x08, # 0x1C
                       0x08, 0x0A, 0x00, 0x04, # 0x20
                       0x04, 0x04, 0x00, None, # 0x24
                       None, None, None, None, # 0x28
                       None, None, None, None, # 0x2C
                       None,
                       0x50, 0x52, 0x49, 0x31, # 0x31 Extended Query
                       0x31, 0x0A, 0x00, 0x00, # 0x35
                       0x00, 0x01, 0x01, 0x00, # 0x39
                       0x33, 0x00, 0x01, 0x80, # 0x3D
                       0x00, 0x03, 0x03, 0x03, # 0x41
                       0x00],                  # 0x45
        "device_id" : None,
        "manufacturer_id" : 0x0089,     # Intel
        "max_chip_width" : 16,          # 16-bits chips
        "unit_size" : None,
        "intel_write_buffer" : 1,
        "intel_protection_program" : 1,
        "intel_configuration" : 1,
        "intel_lock" : 1                # simple locking
        },

    "28F___M29EW_": {                #
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, # 0x10 Query Unique ASCII String 'QRY'
                       0x02, 0x00, # 0x13 Primary algorithm command set and
                                   # control interface ID code - AMD
                       0x40, 0x00, # 0x15 Address for primary algorithm extended
                                   # query table P = 40h
                       0x00, 0x00, # 0x17 Alternative vendor command set and
                                   # control interface ID code
                       0x00, 0x00, # 0x19 Address for alternate algorithm
                                   # extended query table
                       0x27, # 0x1b Vcc logic supply minimum Voltage
                       0x36, # 0x1c Vcc logic supply maximum
                       0xb5, # 0x1d Vpph supply minimum
                       0xc5, # 0x1e Vpph supply maximum
                       0x09, # 0x1f timeout for single byte/word program
                       0x0a, # 0x20 timeout for max size buffer 2^n us
                       0x0a, # 0x21 timeout for individual block erase
                       0x12, # 0x22 timeout for full chip erase 2^n ms
                             # 0x12,0x13,0x14,0x15
                       0x01, # 0x23 timeout for byte/word program
                       0x02, # 0x24 timeout for buffer program
                       0x02, # 0x25 timeout for individual block erase
                       0x02, # 0x26 timeout for chip erase 2^n seconds
                       0x19, # 0x27 Device Size = 2^n bytes 0x19,0x1a,0x1b,0x1c
                       0x02, 0x00, # 0x28 flash device interface code
                                   # description x8, x16, async
                       0x0a, 0x00, # 0x2a maximum bytes in multi-byte program
                                   # or page = 2^n
                       0x01, # 0x2c number of erase block regions.
                       0xff, 0x00, # 0x2d erase block region 1 information.
                                   # 0xff,{0x00,0x01,0x03,0x07}
                       0x00, 0x02, # 0x2f Erase block region 1 information
                                   # 128kBytes
                       0x00, 0x00, 0x00, 0x00, # 0x31 erase block region 2 info
                       0x00, 0x00, 0x00, 0x00, # 0x35 erase block region 3 info
                       0x00, 0x00, 0x00, 0x00, # 0x39 erase block region 4 info
                       0x00, 0x00, 0x00, # 0x3d-0x3f - Not specified
                       0x50, 0x52, 0x49, # 0x40 Primary extended query table
                                         # ASCII 'PRI'
                       0x31, 0x33, # 0x43 ASCII Major, ASCII Minor ver
                       0x18, # 0x45 Address sensitive unlock
                       0x02, # 0x46 Erase Suspend
                       0x01, # 0x47 Block protection
                       0x00, # 0x48 Temporary block protect
                       0x08, # 0x49 Block Protect/unprotect
                       0x00, # 0x4a Simultaneous operations -> not supported
                       0x00, # 0x4b Burst mode -> not supported
                       0x03, # 0x4c Page Mode -> 16-word page
                       0xb5, # 0x4d Vpph supply minimum voltage
                       0xc5, # 0x4e Vpph supply maximum voltage
                       0x04, # 0x4f Top/Bottom boot block flag
                             # 0x04 -> HW protect low, 0x05 -> protect high
                       0x01, # 0x50 Program suspend -> not supported
                       ],

        "device_id": None,
        "manufacturer_id": 0x89,  # Intel
        "max_chip_width": 16,     # 16-bits chip
        "unit_size": None,
        "write_buffer_size": 1024,
        },

    "82802-8": {                       # Intel® 82808AB/82802AC (FWH)
        "device_id": 0xAC,
        "manufacturer_id": 0x89,       # Intel
        "max_chip_width": 8,
        "unit_size": [0x10000 for i in range(16)],
        "intel_write_buffer": 1,
        "intel_lock": 1,               # simple locking
        "command_set": 0x0001,          # Intel command-set, since no CFI structure
        },

    "Am29F040B": {
        "device_id" : 0xA4,
        "manufacturer_id" : 0x01,       # AMD
        "max_chip_width" : 8,           # 8-bits chips
        "command_set": 0x0002,          # AMD command-set, since no CFI structure
        "unit_size" : [0x10000 for i in range(8)]
        },

    "AT49BV001A": {
        "device_id" : 0x05,
        "manufacturer_id" : 0x1f,  # Atmel
        "max_chip_width" : 8,
        "command_set" : 0x0002,
        "unit_size" : [ 0x4000, 0x2000, 0x2000, 0x8000, 0x10000 ]
        },

    "AT49BV001AT": {
        "device_id" : 0x04,
        "manufacturer_id" : 0x1f,  # Atmel
        "max_chip_width" : 8,
        "command_set" : 0x0002,
        "unit_size" : [ 0x10000, 0x8000, 0x2000, 0x2000, 0x4000 ]
        },

    "Am29BDS___": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x17, # 0x18
                       0x19, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x09, 0x00, 0x04, # 0x20
                       0x00, 0x04, 0x00, None, # 0x24
                       0x01, 0x00, 0x00, 0x00, # 0x28
                       0x03, 0x07, 0x00, 0x20, # 0x2C
                       0x00, None, 0x00, 0x00, # 0x30
                       0x01, 0x07, 0x00, 0x20, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x0C, 0x02, 0x01, # 0x44
                       0x00, 0x07, None, 0x01, # 0x48
                       0x00, 0xB5, 0xC5, 0x01, # 0x4C
                       0x00, 0x00, 0x00, 0x00, # 0x50
                       0x00, 0x00, 0x00, 0x04, # 0x54
                       None, None, None, None],# 0x58
        "device_id": None,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,          # 8-bits chips
        "unit_size": None,
        },
    "Am29F016D": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x45, # 0x18
                       0x55, 0x00, 0x00, 0x03, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x15, # 0x24
                       0x00, 0x00, 0x00, 0x00, # 0x28
                       0x01, 0x1F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x31, 0x00, 0x02, 0x04, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 0xAD,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 8,           # 8-bits chips
        "unit_size": [0x10000 for i in range(32)],
        },

    "Am29SL160CT": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x18, # 0x18
                       0x22, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x15, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x02, 0x07, 0x00, 0x20, # 0x2C
                       0x00, 0x1E, 0x00, 0x00, # 0x30
                       0x01, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x30, 0x00, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 0x22A4,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "unit_size": [0x10000 for i in range(31)] + [0x2000 for i in range(8)],
        },
     "Am29LV640MH": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0A, 0x00, 0x01, # 0x20
                       0x05, 0x04, 0x00, 0x17, # 0x24
                       0x02, 0x00, 0x05, 0x00, # 0x28
                       0x01, 0x7F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x08, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x01, 0xB5, 0xC5, 0x05, # 0x4C
                       0x01],                  # 0x50
        "device_id": [0x227E, 0x220C, 0x2201],
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "unit_size": [0x10000 for i in range(128)],
        },
     "Am29LV64_D": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x17, # 0x24
                       0x01, 0x00, 0x00, 0x00, # 0x28
                       0x01, 0x7F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x00, 0x02, 0x04, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0xB5, 0xC5, 0x05], # 0x4C
        "device_id": 0x22D7,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "unit_size": [0x10000 for i in range(128)],
        },
    "Am29DL323G_": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x16, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x02, 0x07, 0x00, 0x20, # 0x2C
                       0x00, 0x3e, 0x00, 0x00, # 0x30
                       0x01, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x04, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x30, 0x00, # 0x48
                       0x00, 0x85, 0x95, None],# 0x4C
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bit chip
        },
    "Am29LV033C": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x16, # 0x24
                       0x00, 0x00, 0x00, 0x00, # 0x28
                       0x01, 0x3F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x30, 0x01, 0x02, 0x01, # 0x44
                       0x04, 0x04, 0x20, 0x00, # 0x48
                       0x00, 0xB5, 0xC5, 0x05],# 0x4C
        "manufacturer_id": 0x01,       # AMD
        "device_id": 0xa3,
        "max_chip_width": 8,           # 8-bit chip
        "unit_size": [0x10000]*64,
        },
    "SG29GL064M": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0A, 0x00, 0x01, # 0x20
                       0x05, 0x04, 0x00, 0x17, # 0x24
                       0x02, 0x00, 0x05, 0x00, # 0x28
                       0x01, 0x7F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x08, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x01, 0xB5, 0xC5, 0x05, # 0x4C
                       0x01],                  # 0x50
        "device_id": [0x227E, 0x220C, 0x2201],
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "unit_size": [0x10000 for i in range(128)],
        },

    "Am29LV800BB": {
        "device_id": 0x225b,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "command_set": 0x0002,          # AMD command-set, since no CFI structure
        "unit_size": [0x4000, 0x2000, 0x2000, 0x8000]
                      + [0x10000 for i in range(15)],
        },

    "Am29LV800BT": {
        "device_id": 0x22da,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "command_set": 0x0002,          # AMD command-set, since no CFI structure
        "unit_size": [0x10000 for i in range(15)]
                      + [0x8000, 0x2000, 0x2000, 0x4000],
        },

    "Am29LV160MB": {
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x00, 0x0A, 0x00, 0x01, # 0x20
                       0x00, 0x04, 0x00, 0x15, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x04, 0x00, 0x00, 0x40, # 0x2C
                       0x00, 0x01, 0x00, 0x20, # 0x30
                       0x00, 0x00, 0x00, 0x80, # 0x34
                       0x00, 0x1E, 0x00, 0x00, # 0x38
                       0x01, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x08, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00],                  # 0x4C
        "device_id": 0x2249,
        "manufacturer_id": 0x01,       # AMD
        "max_chip_width": 16,           # 16-bits chip
        "unit_size": [0x4000, 0x2000, 0x2000, 0x8000] + [0x10000 for i in range(31)],
        },

    "MBM29LV650UE": {
        "cfi_query": [0x04, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x17, # 0x24
                       0x01, 0x00, 0x05, 0x00, # 0x28
                       0x01, 0x7F, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x31, 0x01, 0x02, 0x04, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0xB5, 0xC5, 0x05], # 0x4C
        "device_id": 0x22d7,
        "manufacturer_id": 0x04,       # Spansion/Fujitsu
        "max_chip_width": 16,          # 16-bits chip
        "amd_ignore_cmd_address": 1,
        "unit_size": [0x10000 for i in range(128)],
        },

    "S29GL___M_": {
        "cfi_query": [0x04, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0A, 0x00, 0x01, # 0x20
                       0x05, 0x04, 0x00, None, # 0x24
                       None, 0x00, 0x05, 0x00, # 0x28
                       None, None, None, None, # 0x2C
                       None, None, 0x00, 0x00, # 0x30
                       None, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, None, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x01, 0xB5, 0xC5, None, # 0x4C
                       0x01], # 0x50
        "device_id": None,
        "manufacturer_id": 0x01,
        "max_chip_width": None,          # 16-bits chip
        },

    "S29GL___N": {
        "cfi_query": [0x04, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0A, 0x00, 0x01, # 0x20
                       0x05, 0x04, 0x00, None, # 0x24
                       0x02, 0x00, 0x05, 0x00, # 0x28
                       0x01, None, None, 0x00, # 0x2C
                       0x02, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x10, 0x02, 0x01, # 0x44
                       0x00, 0x08, 0x00, 0x00, # 0x48
                       0x02, 0xB5, 0xC5, None, # 0x4C
                       0x01], # 0x50
        "device_id": None,
        "manufacturer_id": 0x01,
        "max_chip_width": 16,          # 16-bits chip
        },

    "S29GL___P": {
        "cfi_query" : [0x04, 0x00, 0x00, 0x00, # 0x00
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
        "write_buffer_size" : 64,
        "timing_model" : {
            # supports repeated sector erase within 50 µs
            'AMD Erase In Progress': 50e-6 }
        },

    "S29GL064A": {
        "cfi_query" : [0x04, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x07, # 0x1C
                       0x07, 0x0a, 0x00, 0x01, # 0x20
                       0x05, 0x04, 0x00, 0x17, # 0x24
                       0x02, 0x00, 0x05, 0x00, # 0x28
                       0x01, 0x7f, 0x00, 0x00, # 0x2C
                       0x01, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x08, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x01, 0xB5, 0xC5, 0x04, # 0x4C
                       0x01], # 0x50
        "device_id" : [0x00, 0x01, 0x0e, 0x0f],
        "manufacturer_id" : 0x00,
        "max_chip_width" : 16,          # 16-bits chip
        "unit_size" : [64*1024]*128
        },

    "S29AL016D-1": { # top boot sector
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x15, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x04, 0x00, 0x00, 0x40, # 0x2C
                       0x00, 0x01, 0x00, 0x20, # 0x30
                       0x00, 0x00, 0x00, 0x80, # 0x34
                       0x00, 0x1E, 0x00, 0x00, # 0x38
                       0x01, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x30, 0x00, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 0x22c4,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "unit_size": [0x10000 for i in range(31)] + [0x8000, 0x2000, 0x2000, 0x4000],
        },

    "S29AL016D-2": { # bottom boot sector
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x15, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x04, 0x00, 0x00, 0x40, # 0x2C
                       0x00, 0x01, 0x00, 0x20, # 0x30
                       0x00, 0x00, 0x00, 0x80, # 0x34
                       0x00, 0x1E, 0x00, 0x00, # 0x38
                       0x01, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x30, 0x00, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 2249,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "unit_size": [0x4000, 0x2000, 0x2000, 0x8000] + [0x10000 for i in range(31)],
        },

    "S29AL004D-1": {                   # top boot sector
        "device_id": 0x22b9,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "command_set": 0x0002,          # AMD command-set, since no CFI structure
        "unit_size": [0x10000 for i in range(7)] + [0x8000, 0x2000, 0x2000, 0x4000],
        },

    "S29AL008J-1": { # top boot sector
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x14, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x04, 0x00, 0x00, 0x40, # 0x2C
                       0x00, 0x01, 0x00, 0x20, # 0x30
                       0x00, 0x00, 0x00, 0x80, # 0x34
                       0x00, 0x0E, 0x00, 0x00, # 0x38
                       0x01, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x00, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 0x22da,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "unit_size": [0x10000 for i in range(15)] + [0x8000, 0x2000, 0x2000, 0x4000],
        },

    "S29AL008J-2": { # bottom boot sector
        "cfi_query": [0x01, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x04, # 0x1C
                       0x00, 0x0A, 0x00, 0x05, # 0x20
                       0x00, 0x04, 0x00, 0x14, # 0x24
                       0x02, 0x00, 0x00, 0x00, # 0x28
                       0x04, 0x00, 0x00, 0x40, # 0x2C
                       0x00, 0x01, 0x00, 0x20, # 0x30
                       0x00, 0x00, 0x00, 0x80, # 0x34
                       0x00, 0x0E, 0x00, 0x00, # 0x38
                       0x01, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x00, 0x02, 0x01, # 0x44
                       0x01, 0x04, 0x00, 0x00, # 0x48
                       0x00, 0x00, 0x00, 0x00],# 0x4C
        "device_id": 0x225b,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "unit_size": [0x4000, 0x2000, 0x2000, 0x8000] + [0x10000 for i in range(15)],
        },

    "S29AL004D-2": {                   # bottom boot sector
        "device_id": 0x22ba,
        "manufacturer_id": 0x01,       # Spansion
        "max_chip_width": 16,          # 16-bits chips
        "command_set": 0x0002,          # AMD command-set, since no CFI structure
        "unit_size": [0x4000, 0x2000, 0x2000, 0x8000] + [0x10000 for i in range(7)],
        },

    "SST39VF040": {                    # 4 Mbit - 512 Kbytes
        "device_id": 0xd7,
        "manufacturer_id": 0xBF,       # SST
        "max_chip_width": 8,           # 8-bit chip
        "command_set": 0x0001,          # Intel command-set, since no CFI structure
        "unit_size": [0x1000 for i in range(128)],
        },

    # descriptions for Macronix Flash
    #
    # when trying to add a new configuration of Macronix Flash,
    # please try to modify this entry first instead of adding
    # a new entry if possible, substitute '_' for corresponding
    # characters, and do reconfiguration in finish_config_MX29GL256E_
    # (name of the completion function needs to be modified too)
    "MX29GL256E_": {
        "cfi_query": [0x00, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0x00, 0x00, 0x03, # 0x1C
                       0x06, 0x09, 0x13, 0x03, # 0x20
                       0x05, 0x03, 0x02, 0x19, # 0x24
                       0x02, 0x00, 0x06, 0x00, # 0x28
                       0x01, 0xff, 0x00, 0x00, # 0x2C
                       0x02, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x14, 0x02, 0x01, # 0x44
                       0x00, 0x08, 0x00, 0x00, # 0x48
                       0x02, 0x95, 0xa5, 0x04, # 0x4c
                       0x1],                   # 0x50
        "device_id": [0x227e, 0x2222, 0x2201],
        "manufacturer_id": 0xc2,       # Macronix
        "max_chip_width": 16,          # support 8/16 bits
        "unit_size": [0x20000 for i in range(256)],
        "write_buffer_size": 64,
        },

    # descriptions for Micron __28F___M29EW__
    "__28F___M29EW__": {
        "cfi_query": [0x00, 0x00, 0x00, 0x00, # 0x00
                       0x00, 0x00, 0x00, 0x00, # 0x04
                       0x00, 0x00, 0x00, 0x00, # 0x08
                       0x00, 0x00, 0x00, 0x00, # 0x0C
                       0x51, 0x52, 0x59, 0x02, # 0x10
                       0x00, 0x40, 0x00, 0x00, # 0x14
                       0x00, 0x00, 0x00, 0x27, # 0x18
                       0x36, 0xb5, 0xc5, 0x09, # 0x1C
                       0x0a, 0x0a, 0x12, 0x01, # 0x20
                       0x02, 0x02, 0x02, 0x19, # 0x24
                       0x02, 0x00, 0x0a, 0x00, # 0x28
                       0x01, 0xff, 0x00, 0x00, # 0x2C
                       0x02, 0x00, 0x00, 0x00, # 0x30
                       0x00, 0x00, 0x00, 0x00, # 0x34
                       0x00, 0x00, 0x00, 0x00, # 0x38
                       0x00, 0x00, 0x00, 0x00, # 0x3C
                       0x50, 0x52, 0x49, 0x31, # 0x40
                       0x33, 0x18, 0x02, 0x01, # 0x44
                       0x00, 0x08, 0x00, 0x00, # 0x48
                       0x03, 0xb5, 0xc5, 0x04, # 0x4C
                       0x01,                   # 0x50
                       ],

        "device_id": None,
        "manufacturer_id": 0x89,
        "max_chip_width": 16,    # support 8/16 bits
        "unit_size": None,
        "write_buffer_size": 1024,
        },
    }


##############################
# End of flash configuration #
##############################

# return 0 if not matching, 1 if matching
def compare_product_no(str1, str2):
    l1 = len(str1)
    l2 = len(str2)
    if l1 != l2:
        return 0
    else:
        for i in range(0, l2):
            if str1[i] != "_" and str1[i] != str2[i]:
                return 0
        return 1

def match_product_no(def_list, product_no):
    for p in list(def_list.keys()):
        if compare_product_no(p, product_no):
            return p
    return None

@cli.doc('add a new flash model',
     return_value = '''True if the flash model was successfully added,
or False if it failed.''')
def flash_add_model(product_no, config, complete_func):
    '''Adds a new flash model. Instances of the new flash can then be created
    with the <fun>flash_create_memory</fun> and
    <fun>flash_create_memory_anon</fun> functions.

    These are the arguments:
    <dl>
      <dt><param>product_no</param></dt>
        <dd>Product number; e.g., "28F___C3_". Underscores act as wild cards
            and will match any character.</dd>
      <dt><param>config</param></dt>
         <dd>Dictionary containing <attr>attribute</attr>: value pairs. These
             attributes are <class>generic-flash-memory</class> attributes;
             information on available attributes and how to configure them can
             be found in the reference manual.</dd>
      <dt><param>complete_fun</param></dt>
         <dd>Function of type <fun>complete_fun(product_no, config)</fun> that
             will be called just before a flash memory is instantiated.
             <param>product_no</param> is the product number specified by the
             user. <param>config</param> is the same <param>config</param>
             dictionary as passed to the <fun>flash_add_model</fun> function.
             The <fun>complete_fun</fun> can modify the attribute values, add
             new attributes or remove attributes from the configuration, based
             on e.g. the <param>product_no</param>. The <fun>complete_fun</fun>
             should return either an error message (i.e. a string), or a tuple
             (<param>updated_config</param>, <param>size</param>) where
             <param>size</param> is the size of one flash chip, in bytes.</dd>
    </dl>'''

    global flash_descriptions

    if match_product_no(flash_descriptions, product_no):
        print("flash '%s' already exists" % product_no)
        return False


    flash_descriptions[product_no] = config

    assert not product_no in complete_functions
    complete_functions[product_no] = complete_func

    return True

@cli.doc('create a list of objects representing a flash memory',
     return_value = 'tuple(object dict, total size in bytes)')
def flash_create_memory(name, product_no, interleave, bus_width,
                        files = [],
                        queue = None,
                        accept_smaller_reads = 1,
                        accept_smaller_writes = 0,
                        big_endian = 0):
    '''Returns a list of pre_objects suitable as input for
    <fun>SIM_add_configuration</fun> and the total size in bytes of the flash
    memory. The list and the size is returned as a tuple.

    The flash objects will be named, which makes them suitable for use in legacy
    components. New components should use the function
    <fun>flash_create_memory_anon</fun> instead.

    Function arguments:
    <dl>
      <dt><param>name</param></dt>
         <dd>Base name for all objects (flash, ram, and image).</dd>
      <dt><param>product_no</param></dt>
         <dd>Product name; e.g., "28F160C3T".</dd>
      <dt><param>interleave</param></dt>
         <dd>Byte interleaving; one of 1, 2, 4, and 8.</dd>
      <dt><param>bus_width</param></dt>
         <dd>Bus width; one of 8, 16, 32, and 64.</dd>
      <dt><param>files</param></dt>
         <dd>Same as the <attr>file</attr> attribute of <class>image</class>
         objects. Defaults to the empty list.</dd>
      <dt><param>queue</param></dt>
         <dd>Queue object to use.</dd>
      <dt><param>accept_smaller_reads</param></dt>
         <dd>If 1 (default), the flash device will accept reads smaller than
             the bus width. if 0, the flash device will complain when receiving
             smaller reads.
         </dd>
      <dt><param>accept_smaller_writes</param></dt>
         <dd>If 1, the flash device will accept writes smaller than the bus
             width. If 0 (default), the flash device will complain when
             receiving smaller writes.
         </dd>
      <dt><param>big_endian</param></dt>
         <dd>If set, the flash device will behave as a big endian device. If
             not set (default), it will behave as a little endian device.
         </dd>
    </dl>'''
    [flash_obj, ram_obj, image_obj], size = _flash_create_memory(
        'flash_create_memory',
        product_no, interleave, bus_width, files, queue,
        accept_smaller_reads, accept_smaller_writes, big_endian, name)
    return ({ name: flash_obj, name + '_ram': ram_obj,
              name + '_image': image_obj }, size)

@cli.doc('create a list of objects representing a flash memory',
     return_value = 'tuple(object list, total size in bytes)')
def flash_create_memory_anon(product_no, interleave, bus_width,
                             files = [],
                             queue = None,
                             accept_smaller_reads = 1,
                             accept_smaller_writes = 0,
                             big_endian = 0):
    '''Returns an list of pre_objects suitable as input for
    <fun>SIM_add_configuration</fun> and the total size in bytes of the flash
    memory. The list and the size is returned as a tuple.

    The flash objects will be anonymous, which makes them suitable for use in
    new components. Legacy components should use the function
    <fun>flash_create_memory</fun> instead.

    Function arguments:
    <dl>
      <dt><param>product_no</param></dt>
         <dd>Product name; e.g., "28F160C3T".</dd>
      <dt><param>interleave</param></dt>
         <dd>Byte interleaving; one of 1, 2, 4, and 8.</dd>
      <dt><param>bus_width</param></dt>
         <dd>Bus width; one of 8, 16, 32, and 64.</dd>
      <dt><param>files</param></dt>
         <dd>Same as the <attr>file</attr> attribute of <class>image</class>
         objects. Defaults to the empty list.</dd>
      <dt><param>queue</param></dt>
         <dd>Queue object to use.</dd>
      <dt><param>accept_smaller_reads</param></dt>
         <dd>If 1 (default), the flash device will accept reads smaller than
             the bus width. if 0, the flash device will complain when receiving
             smaller reads.
         </dd>
      <dt><param>accept_smaller_writes</param></dt>
         <dd>If 1, the flash device will accept writes smaller than the bus
             width. If 0 (default), the flash device will complain when
             receiving smaller writes.
         </dd>
      <dt><param>big_endian</param></dt>
         <dd>If set, the flash device will behave as a big endian device. If
             not set (default), it will behave as a little endian device.
         </dd>
    </dl>'''
    return _flash_create_memory(
        'flash_create_memory_anon',
        product_no, interleave, bus_width, files, queue,
        accept_smaller_reads, accept_smaller_writes, big_endian, None)

def _flash_create_memory(calling_function,
                         product_no, interleave, bus_width,
                         files,
                         queue,
                         accept_smaller_reads,
                         accept_smaller_writes,
                         big_endian,
                         name):
    # find the description
    pn = match_product_no(flash_descriptions, product_no)
    if not pn:
        print("%s():" % (calling_function,))
        print("  No product were found matching the product number '" + product_no + "'")
        print("  It should be one of the following (with '_' replaced by an appropriate letter or number):")
        print(" ", list(flash_descriptions.keys()))
        return

    config = copy.deepcopy(flash_descriptions[pn])
    ret = complete_functions[pn](product_no, config)

    if isinstance(ret, type("")):
        print("%s():" % (calling_function,))
        print("  " + ret)
        return
    else:
        (config, size) = ret

    # compute the total size
    size *= interleave

    image_obj = pre_obj(name + '_image' if name else '', 'image',
                        size = size,
                        files = files,
                        init_pattern = 0xff)
    ram_obj = pre_obj(name + '_ram' if name else '', 'ram', image = image_obj)

    # complete the configuration
    config['interleave'] = interleave
    config['bus_width'] = bus_width
    config['accept_smaller_reads'] = accept_smaller_reads
    config['accept_smaller_writes'] = accept_smaller_writes
    config['big_endian'] = big_endian
    config['storage_ram'] = ram_obj
    flash_obj = pre_obj(name if name else '', 'generic-flash-memory', **config)

    if queue:
        flash_obj.queue = image_obj.queue = queue

    return ([flash_obj, ram_obj, image_obj], size)
