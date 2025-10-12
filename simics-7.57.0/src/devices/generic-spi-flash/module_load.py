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
# ------------------------ info -----------------------
#

def get_info(obj):
    return [(None, [('Flash size', '%dMbit' % (obj.sector_size // 1024 * obj.sector_number // 128)),
                    ('image',      obj.mem_block)])]

cli.new_info_command('generic_spi_flash', get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    status = obj.fcl_status
    area = (status >> 2) & 7
    if area != 0:
        area = 1 << (area - 1)
    return [(None,
             [('WP', ('disabled', 'enabled')[obj.fcl_hwwp != 0]),
              ('WIP', status & 1),
              ('Protected Area', str([i for i in range(16)][(16 - area):]))]
            )]

cli.new_status_command('generic_spi_flash', get_status)
