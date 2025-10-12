# © 2023 Intel Corporation
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
import ctypes


class translation_proxy:
    cls = simics.confclass("translation-proxy")
    cls.attr.target("o", default=None)
    cls.attr.expected_base("i", default=0)
    cls.attr.expected_size("i", default=ctypes.c_uint64(-1).value)
    cls.attr.expected_access(
        "i",
        default=(
            simics.Sim_Access_Read | simics.Sim_Access_Write | simics.Sim_Access_Execute
        ),
    )
    cls.attr.device_id("i", default=0)

    @cls.attr.target.setter
    def target_set(self, val):
        self.target = val
        if hasattr(self, "map_target") and self.map_target is not None:
            simics.SIM_free_map_target(self.map_target)
        self.map_target = simics.SIM_new_map_target(self.target, None, None)

    @cls.iface.transaction_translator.translate
    def translate(self, addr, access, t, callback, cbdata):
        assert self.target is not None
        txl = simics.translation_t(target=self.map_target)
        return callback(txl, t, cbdata)

    @cls.iface.translation_flush.flush_range
    def flush_range(self, base, size, access, default_target):
        stest.expect_equal(base, self.expected_base)
        stest.expect_equal(size, self.expected_size)
        stest.expect_equal(access, self.expected_access)
        simics.SIM_log_info(
            1, self.obj, 0, f"Device '{self.obj.name}' flush_ranges triggered"
        )
        return simics.SIM_map_target_flush(self.map_target, base, size, access)


def set_proxy_target(target_proxy: simics.conf_object_t, target: simics.conf_object_t):
    target_proxy.iface.map_demap.map_simple(target, None, simics.map_info_t())


def new_ram_proxy() -> simics.conf_object_t:
    img = simics.pre_conf_object(None, "image", size=1024)
    ram = simics.pre_conf_object(None, "ram", image=img)
    ram_proxy = simics.pre_conf_object(None, "translation-proxy")
    ram_proxy.target = ram
    simics.SIM_add_configuration([img, ram, ram_proxy], None)
    return simics.SIM_get_object(ram_proxy.name)


def validate_flush(
    target_proxy: simics.conf_object_t,
    rp: simics.conf_object_t,
    t: simics.transaction_t,
    addr: int = 0,
):
    target_proxy.iface.direct_memory_lookup_v2.lookup(
        t, addr, simics.Sim_Access_Write if t.write else simics.Sim_Access_Read
    )

    with stest.expect_log_mgr(log_type="info", regex="flush_ranges triggered"):
        map_target = simics.SIM_new_map_target(rp, None, None)
        ret = simics.SIM_map_target_flush(
            map_target,
            0,
            ctypes.c_uint64(-1).value,
            (
                simics.Sim_Access_Read
                | simics.Sim_Access_Write
                | simics.Sim_Access_Execute
            ),
        )
        stest.expect_true(ret)
        simics.SIM_free_map_target(map_target)


def test_dmi(
    dmi: simics.conf_object_t,
    target_proxy: simics.conf_object_t,
    dummy_gfx_obj: simics.conf_object_t,
):
    set_proxy_target(target_proxy, dmi)

    def test_default_remapping_unit(ram_proxy: simics.conf_object_t):
        simics.SIM_set_attribute(dmi, "default_remapping_unit", ram_proxy)
        t = simics.transaction_t(read=True, pcie_type=simics.PCIE_Type_Mem)
        validate_flush(target_proxy, dmi, t)
        simics.SIM_set_attribute(dmi, "default_remapping_unit", None)

    def test_gfx_remapping_unit(ram_proxy: simics.conf_object_t):
        dmi.gfx_objs = [dummy_gfx_obj]
        simics.SIM_set_attribute(dmi, "gfx_remapping_unit", ram_proxy)
        t = simics.transaction_t(
            read=True, pcie_type=simics.PCIE_Type_Mem, initiator=dmi.gfx_objs[0]
        )
        validate_flush(target_proxy, dmi, t)
        simics.SIM_set_attribute(dmi, "gfx_remapping_unit", None)
        dmi.gfx_objs = []

    test_default_remapping_unit(new_ram_proxy())
    test_gfx_remapping_unit(new_ram_proxy())


def main():
    dmi = simics.pre_conf_object("dmi", "x58-dmi")
    target_proxy_dmi = simics.pre_conf_object("target_proxy_dmi", "memory-space")
    dummy_gfx_obj = simics.pre_conf_object("dummy", "dummy")

    simics.SIM_add_configuration([dmi, target_proxy_dmi, dummy_gfx_obj], None)

    dmi = simics.SIM_get_object(dmi.name)
    target_proxy_dmi = simics.SIM_get_object(target_proxy_dmi.name)
    dummy_gfx_obj = simics.SIM_get_object(dummy_gfx_obj.name)

    test_dmi(dmi, target_proxy_dmi, dummy_gfx_obj)


main()
