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

import conf
import simics
import stest


def test(checkpoint):
    cpfile = stest.scratch_file("checkpoint")
    with open(cpfile, 'wb') as f:
        f.write(checkpoint)
    simics.SIM_read_configuration(cpfile)
    stest.expect_equal(conf.dp.conf_space.classname, 'memory-space')
    stest.expect_equal(
        conf.dp.conf_space.default_target,
        [conf.dp.impl.conf_to_cfg, 0, 0, conf.dp.cfg_space, 0, 0])
    simics.SIM_delete_objects([conf.dp])


ms_checkpoint = b"""
OBJECT sim TYPE sim {
    version: 0x17f5
    build_id: 0x17f5
}
OBJECT dp TYPE pcie-downstream-port-legacy {
    build_id: 0x17f7
}
OBJECT dp.cfg_space TYPE memory-space {
    build_id: 0x17f5
}
OBJECT dp.conf_space TYPE memory-space {
    build_id: 0x17f5
    default_target: (dp.port.conf_translator,0,0,dp.cfg_space,0,0)
}
OBJECT dp.port.conf_translator TYPE pcie-downstream-port-legacy.conf_translator {
    build_id: 0x17f5
}
"""

subdev_checkpoint = b"""
OBJECT sim TYPE sim {
    version: 0x1828
    build_id: 0x1828
}
OBJECT dp TYPE pcie-downstream-port-legacy {
    build_id: 0x1828
}
OBJECT dp.cfg_space TYPE memory-space {
    build_id: 0x1829
}
OBJECT dp.conf_space TYPE pcie-downstream-port-legacy.conf_space {
    build_id: 0x1828
}
OBJECT dp.port.conf_translator TYPE pcie-downstream-port-legacy.conf_translator {
    build_id: 0x1828
}
"""
test(ms_checkpoint)
test(subdev_checkpoint)
