# © 2014 Intel Corporation
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

def mmc_get_info(obj):
    def card_type():
        t = obj.card_type
        if t >= 0 and t < 4:
            return ('MMC', 'SD', 'SDHC', 'SDIO')[t]
        else:
            return 'UNKNOWN'

    def card_size():
        return str(obj.size >> 20) + 'MB'

    return [(None,
              [ ('Type', card_type()),
                ('Size', card_size()),
                ("Flash Image", obj.flash_image)])]

def mmc_get_status(obj):
    def card_address():
        return obj.ivp_state['MMC.Card']['RCA']

    def card_state():
        return ('Idle',
                'Ready',
                'Identification',
                'Standby',
                'Transfer',
                'Sending_Data',
                'Bus_Test',
                'Receive_Data',
                'Programming',
                'Disconnect',
                'Sleep',
                'Inactive',
                'Wait_Irq',
                'Invalid',
                'Invalid',
                'Invalid')[obj.ivp_state['MMC.Card']['State'] & 0xF]

    return [(None,
             [('Address', card_address()),
              ('State', card_state())])]

cli.new_info_command('generic-mmc-card', mmc_get_info)
cli.new_status_command('generic-mmc-card', mmc_get_status)
