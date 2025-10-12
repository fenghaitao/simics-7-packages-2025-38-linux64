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


import simics

def create_sample_802_15_4_transceiver(name=None):
    '''Create a new sample_802_15_4_transceiver object'''
    sample_802_15_4_transceiver = simics.pre_conf_object(name,
                                                 'sample_802_15_4_transceiver')
    simics.SIM_add_configuration([sample_802_15_4_transceiver], None)
    return simics.SIM_get_object(sample_802_15_4_transceiver.name)
