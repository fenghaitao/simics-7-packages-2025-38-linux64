# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from instrumentation import make_tool_commands

make_tool_commands(
    'bank_coverage_tool',
    object_prefix = 'coverage_tool',
    provider_requirements = 'bank_instrumentation_subscribe & register_view',
    provider_names = ('bank', 'banks'),
    new_cmd_doc = ("Creates a new bank coverage tool object which can be"
                   " connected to register banks"""))
