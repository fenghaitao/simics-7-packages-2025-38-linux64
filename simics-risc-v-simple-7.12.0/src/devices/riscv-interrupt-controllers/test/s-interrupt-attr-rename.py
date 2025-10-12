# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import conf
import simics
import stest

ckpt = stest.scratch_file('test.checkpoint')
with open(ckpt, 'w') as f:
    f.write(f"""
#SIMICS-CONF-1
OBJECT plic TYPE riscv-plic {{
  build_id: 6132
  interrupt: (NIL,)
}}
OBJECT sim TYPE sim {{
  build_id: {conf.sim.build_id}
  version: {conf.sim.build_id}
}}""")

simics.SIM_read_configuration(ckpt)
stest.expect_true(hasattr(conf.plic, 'irq_dev'))
stest.expect_false(hasattr(conf.plic, 'interrupt'))
