# © 2017 Intel Corporation
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

def sd_get_info(obj):
    return []

def sd_get_status(obj):
    return []

cli.new_info_command('sd_card', sd_get_info)
cli.new_status_command('sd_card', sd_get_status)

def mmc_get_info(obj):
    return []

def mmc_get_status(obj):
    return []

cli.new_info_command('mmc_card', mmc_get_info)
cli.new_status_command('mmc_card', mmc_get_status)
