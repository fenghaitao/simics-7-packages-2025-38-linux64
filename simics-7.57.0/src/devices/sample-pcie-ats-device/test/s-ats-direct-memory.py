# © 2024 Intel Corporation
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
import dev_util
import stest
import cli


STU = 4
STU_SIZE = 0x1000 << STU
PASID = 0xabcd
UNTRANSLATED_AREA = 0x20000000
TRANSLATED_AREA = 0x800000000

img = simics.SIM_create_object('image', 'dummy_img', [['size', STU_SIZE * 4]])
ram = simics.SIM_create_object('ram', 'dummy_ram', [['image', img]])
ram_mem = simics.SIM_create_object("memory-space", "ram_mem", [])
ram_mem.map = [[TRANSLATED_AREA, ram, 0, 0, ram.image.size]]

atc = simics.SIM_create_object("sample-pcie-ats-endpoint", "atc", PASID=PASID)
ta  = simics.SIM_create_object("sample-pcie-root-complex-ats", "ta",
                                STU=STU,
                                UNTRANSLATED_AREA = UNTRANSLATED_AREA,
                                TRANSLATED_AREA = TRANSLATED_AREA)

#atc.cli_cmds.log_level(level=4)
#ta.cli_cmds.log_level(level=4)

ta.downstream_port.devices = [[0, atc]]
ta.host_memory = ram_mem

pcie_regs = dev_util.bank_regs(atc.bank.pcie_config)
pcie_regs.command.write(dev_util.READ, m=1)
pcie_regs.ats.control.write(dev_util.READ, enable=1, stu = STU)
pcie_regs.pasid.control.write(dev_util.READ, pe=1, epe=1, pme=1, trwpe=1)

atc_memspace = simics.SIM_create_object("memory-space", "atc_memspace", [])
atc_memspace.default_target = [atc.port.device_memory_request, 0, 0, None]

t = simics.transaction_t()
t.size = STU_SIZE

access = simics.Sim_Access_Read | simics.Sim_Access_Write  | simics.Sim_Access_Execute
lookup = atc_memspace.iface.direct_memory_lookup_v2.lookup(t, UNTRANSLATED_AREA, access)

stest.expect_equal(lookup.target, ram)
stest.expect_equal(lookup.offs, 0x0)
stest.expect_equal(lookup.access, access)

lookup = atc_memspace.iface.direct_memory_lookup_v2.lookup(t, UNTRANSLATED_AREA + STU_SIZE, access)

stest.expect_equal(lookup.target, ram)
stest.expect_equal(lookup.offs, STU_SIZE)
stest.expect_equal(lookup.access, access)
