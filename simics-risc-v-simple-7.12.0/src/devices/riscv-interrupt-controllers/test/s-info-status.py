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


import stest
from riscv_intc_common import create_tb

classes = ["riscv_plic", "riscv_clint"]

tb = create_tb()

# Run info and status on each object. It is difficult to test whether
# the output is informative, so we just check that the commands
# complete nicely.
for cls in classes:
    obj = list(SIM_object_iterator_for_class(cls))[0]
    for cmd in ['info', 'status']:
        try:
            SIM_run_command(obj.name + '.' + cmd)
        except SimExc_General as e:
            stest.fail(cmd + ' command failed: ' + str(e))
