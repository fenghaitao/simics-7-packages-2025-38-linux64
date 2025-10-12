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
import random

STU = 4
STU_SIZE = 0x1000 << STU
PASID = 0xabcd
UNTRANSLATED_AREA = 0x20000000
TRANSLATED_AREA = 0x800000000

class fake_host_memory:
    cls = simics.confclass('host_memory')
    cls.iface.transaction()
    cls.attr.org_addr('i|n', default=None)
    cls.attr.size('i|n', default=None)

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        stest.expect_equal(t.pcie_pasid, PASID)
        stest.expect_equal(t.pcie_at, simics.PCIE_AT_Translated)
        stest.expect_equal(addr, self.org_addr + (TRANSLATED_AREA - UNTRANSLATED_AREA))
        self.org_addr += STU_SIZE

        return simics.Sim_PE_No_Exception

clock = simics.SIM_create_object('clock', 'clock', freq_mhz=1)
mem = simics.SIM_create_object("host_memory", "mem")
atc = simics.SIM_create_object("sample-pcie-ats-endpoint", "atc", PASID=PASID, queue=clock)
ta  = simics.SIM_create_object("sample-pcie-root-complex-ats", "ta",
                                STU=STU,
                                UNTRANSLATED_AREA = UNTRANSLATED_AREA,
                                TRANSLATED_AREA = TRANSLATED_AREA)

#atc.cli_cmds.log_level(level=4)
#ta.cli_cmds.log_level(level=4)

ta.downstream_port.devices = [[0, atc]]
ta.host_memory = mem

pcie_regs = dev_util.bank_regs(atc.bank.pcie_config)
pcie_regs.command.write(dev_util.READ, m=1)
# STU = 3 implies 64k translations for TA
pcie_regs.ats.control.write(dev_util.READ, enable=1, stu = STU)
pcie_regs.pasid.control.write(dev_util.READ, pe=1, epe=1, pme=1, trwpe=1)

atc_mt = simics.SIM_new_map_target(atc.port.device_memory_request, None, None)

t = simics.transaction_t()
t.size = 0x1000
mem.org_addr = 0x20000000
exc = simics.SIM_issue_transaction(atc_mt, t, mem.org_addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(ta.ats_request_ecs_atom, 0)

mem.org_addr = 0x30001000
# To test that extra atoms works in `translation_request_custom()`
atc.extra_atom_in_translation = True
exc = simics.SIM_issue_transaction(atc_mt, t, mem.org_addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(ta.ats_request_ecs_atom, simics.PCIE_ECS_SIG_OS)
atc.extra_atom_in_translation = False

mem.org_addr = 0x20001000
exc = simics.SIM_issue_transaction(atc_mt, t, mem.org_addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)

mem.org_addr = 0x20000000
t.size = STU_SIZE + 0x1000
exc = simics.SIM_issue_transaction(atc_mt, t, mem.org_addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(mem.org_addr, 0x20000000 + (STU_SIZE * 2))

cmd = f"memory-map object = atc.port.device_memory_request"

info, msg = cli.quiet_run_command(cmd)

stest.expect_equal(
    info,
    [
    [UNTRANSLATED_AREA, UNTRANSLATED_AREA + STU_SIZE - 1, "mem", TRANSLATED_AREA, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + STU_SIZE, UNTRANSLATED_AREA + (2 * STU_SIZE) - 1, "mem", TRANSLATED_AREA + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x10000000, UNTRANSLATED_AREA + 0x10000000 + STU_SIZE - 1, "mem", TRANSLATED_AREA + 0x10000000, simics.Sim_Access_Read],
    ]
)

regs = dev_util.bank_regs(ta.bank.regs)

regs.invalidate_addr.write(UNTRANSLATED_AREA)
regs.invalidate_size.write(STU_SIZE)
regs.device_id.write(0)
regs.pasid.write(PASID)
itag = random.randrange(0, 32)
regs.itag.write(dev_util.READ, itag=itag)
regs.invalidate.write(dev_util.READ, invalidate=1)
stest.expect_equal(regs.invalidate.field.result.read(), 1)
stest.expect_equal(regs.itag_vec.read(), 0)
simics.SIM_continue(1)
stest.expect_equal(regs.itag_vec.read(), 1 << itag)

info, msg = cli.quiet_run_command(cmd)

stest.expect_equal(
    info,
    [
    [UNTRANSLATED_AREA + STU_SIZE, UNTRANSLATED_AREA + (2 * STU_SIZE) - 1, "mem", TRANSLATED_AREA + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x10000000, UNTRANSLATED_AREA + 0x10000000 + STU_SIZE - 1, "mem", TRANSLATED_AREA + 0x10000000, simics.Sim_Access_Read],
    ]
)

mem.org_addr = 0x40000000
t.size = STU_SIZE * 3
exc = simics.SIM_issue_transaction(atc_mt, t, mem.org_addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)

info, msg = cli.quiet_run_command(cmd)

stest.expect_equal(
    info,
    [
    [UNTRANSLATED_AREA + STU_SIZE, UNTRANSLATED_AREA + (2 * STU_SIZE) - 1, "mem", TRANSLATED_AREA + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x10000000, UNTRANSLATED_AREA + 0x10000000 + STU_SIZE - 1, "mem", TRANSLATED_AREA + 0x10000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000, UNTRANSLATED_AREA + 0x20000000 + STU_SIZE  - 1, "mem", TRANSLATED_AREA + 0x20000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000 + STU_SIZE, UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2) - 1, "mem", TRANSLATED_AREA + 0x20000000 + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 3) - 1, "mem", TRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), simics.Sim_Access_Read],
    ]
)


regs.invalidate_addr.write(UNTRANSLATED_AREA + 0x20000000 + STU_SIZE)
regs.invalidate_size.write(STU_SIZE)
regs.device_id.write(0)
regs.pasid.write(PASID)
itag = random.randrange(0, 32)
regs.itag.write(itag)
regs.invalidate.write(dev_util.READ, invalidate=1)
stest.expect_equal(regs.invalidate.field.result.read(), 1)
stest.expect_equal(regs.itag_vec.read(), 0)
simics.SIM_continue(1)
stest.expect_equal(regs.itag_vec.read(), 1 << itag)

info, msg = cli.quiet_run_command(cmd)
stest.expect_equal(
    info,
    [
    [UNTRANSLATED_AREA + STU_SIZE, UNTRANSLATED_AREA + (2 * STU_SIZE) - 1, "mem", TRANSLATED_AREA + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x10000000, UNTRANSLATED_AREA + 0x10000000 + STU_SIZE - 1, "mem", TRANSLATED_AREA + 0x10000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000, UNTRANSLATED_AREA + 0x20000000 + STU_SIZE  - 1, "mem", TRANSLATED_AREA + 0x20000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 3) - 1, "mem", TRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), simics.Sim_Access_Read],
    ]
)
simics.SIM_free_map_target(atc_mt)


def save_and_load_checkpoint():
    cpfile = stest.scratch_file("atc")
    simics.SIM_write_configuration_to_file(cpfile, 0)
    names = cli.quiet_run_command('list-objects')[0]
    objs = [simics.SIM_get_object(n) for n in names]
    simics.SIM_delete_objects(objs)
    simics.SIM_read_configuration(cpfile)

save_and_load_checkpoint()

info, msg = cli.quiet_run_command(cmd)
stest.expect_equal(
    info,
    [
    [UNTRANSLATED_AREA + STU_SIZE, UNTRANSLATED_AREA + (2 * STU_SIZE) - 1, "mem", TRANSLATED_AREA + STU_SIZE, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x10000000, UNTRANSLATED_AREA + 0x10000000 + STU_SIZE - 1, "mem", TRANSLATED_AREA + 0x10000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000, UNTRANSLATED_AREA + 0x20000000 + STU_SIZE  - 1, "mem", TRANSLATED_AREA + 0x20000000, simics.Sim_Access_Read],
    [UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), UNTRANSLATED_AREA + 0x20000000 + (STU_SIZE * 3) - 1, "mem", TRANSLATED_AREA + 0x20000000 + (STU_SIZE * 2), simics.Sim_Access_Read],
    ]
)
