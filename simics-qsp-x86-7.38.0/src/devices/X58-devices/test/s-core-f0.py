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

import simics
import stest


class dummy:
    cls = simics.confclass('dummy')
    cls.iface.transaction()


def verify(dev, rus):
    # only inspect the first 5 elements of the map entries
    got_map = [me[:5] for me in dev.remap_space.map]
    expected_map = [[0x1000 * i, dev, 0, 0, 0x1000]
                    for (i, dev) in enumerate(rus)]
    stest.expect_equal(got_map, expected_map)


def test():
    # test default remap units
    dev = simics.SIM_create_object('x58-core', 'dev')
    rus = [d.bank.vtd for d in dev.remap_unit]
    verify(dev, rus)
    simics.SIM_delete_objects([dev])

    # test external remap units
    rus = [simics.SIM_create_object('dummy', f'ru{n}') for n in range(2)]
    dev = simics.SIM_create_object('x58-core', 'dev', external_remap_unit=rus)
    verify(dev, rus)

    # must not change after instantiation
    with stest.expect_log_mgr(dev, log_type="error", regex="instantiation"):
        dev.external_remap_unit = [None, None]
    stest.expect_equal(dev.external_remap_unit, rus)

    simics.SIM_delete_objects([dev] + rus)


test()
