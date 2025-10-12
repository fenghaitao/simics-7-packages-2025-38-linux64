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


import scalar_time

class_name = 'g-cache'

for port in ['transaction',
             'dev_data_read',
             'dev_data_write',
             'c_dev_data_read',
             'c_dev_data_write',
             'uc_data_read',
             'uc_data_write',
             'uc_inst_fetch',
             'data_read',
             'data_read_miss',
             'data_write',
             'data_write_miss',
             'inst_fetch',
             'inst_fetch_miss',
             'copy_back',
             'mesi_exclusive_to_shared',
             'mesi_modified_to_shared',
             'mesi_invalidate']:
    scalar_time.new_scalar_time_port(
        class_name, scalar_time.SimTime, scalar_time.Counts,
        scalar_time.Accumulator, port)
