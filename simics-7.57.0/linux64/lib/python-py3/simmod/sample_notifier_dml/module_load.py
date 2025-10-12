# © 2022 Intel Corporation
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

def get_info(obj):
    return [(None,
             [("Frequency provider", obj.frequency_provider),
              ("Frequency multiplier", obj.multiplier)])]

cli.new_info_command('sample_notifier_dml', get_info)

def get_status(obj):
    return [(None,
             [("Current output frequency",
               obj.frequency_provider and obj.iface.frequency.get())])]

cli.new_status_command('sample_notifier_dml', get_status)
