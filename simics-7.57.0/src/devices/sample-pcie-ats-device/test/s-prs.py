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
import random

STU = 0
STU_SIZE = 0x1000 << STU
UNTRANSLATED_AREA = 0x20000000
TRANSLATED_AREA = 0x800000000

class fake_device_memory:
    cls = simics.confclass('dev_memory')
    cls.iface.transaction()
    cls.attr.exp_addr('i|n', default=None)
    cls.attr.size('i|n', default=None)

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        stest.expect_equal(addr, self.exp_addr)
        self.exp_addr += t.size
        return simics.Sim_PE_No_Exception


class fake_host_memory:
    cls = simics.confclass('host_memory')
    cls.iface.transaction()
    cls.attr.org_addr('i|n', default=None)
    cls.attr.size('i|n', default=None)

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        stest.expect_equal(t.pcie_at, simics.PCIE_AT_Translated)
        stest.expect_equal(addr, self.org_addr + (TRANSLATED_AREA - UNTRANSLATED_AREA))
        self.org_addr += t.size
        print("Host memory received transaction @", hex(addr))
        return simics.Sim_PE_No_Exception


clock = simics.SIM_create_object('clock', 'clock', freq_mhz=1)
host_mem = simics.SIM_create_object("host_memory", "host_mem")
dev_mem = simics.SIM_create_object("dev_memory", "dev_mem")
dma = simics.SIM_create_object("sample-pcie-ats-prs-dma", "dma", device_memory=dev_mem)
ta = simics.SIM_create_object("sample-pcie-root-complex-ats", "ta",
                               STU=STU,
                               UNTRANSLATED_AREA = UNTRANSLATED_AREA,
                               TRANSLATED_AREA = TRANSLATED_AREA,
                               ENABLE_PASID_CHECK = True)

dma.cli_cmds.log_level(level=4)
ta.cli_cmds.log_level(level=4)

ta.downstream_port.devices = [[0, dma]]
ta.host_memory = host_mem

pcie_regs = dev_util.bank_regs(dma.bank.pcie_config)
pcie_regs.command.write(dev_util.READ, m=1)
pcie_regs.ats.control.write(dev_util.READ, enable=1, stu = STU)
pcie_regs.pasid.control.write(dev_util.READ, pe=1, trwpe=1)
pcie_regs.prs.control.write(dev_util.READ, enable=1)

regs = dev_util.bank_regs(dma.bank.regs)
for i in range(8):
    pasid = random.randrange(0, 1 << 20)
    dev_addr = random.randrange(1 << 52) << 12
    host_addr = UNTRANSLATED_AREA + 0x10000 * i
    size = random.choice([8, 64, 0x1000, 0x2000])
    regs.channel[i].dma_dev.write(dev_addr)
    regs.channel[i].dma_host.write(host_addr)
    regs.channel[i].dma_len.write(size)
    regs.channel[i].pasid.write(i)
    regs.channel[i].dma_start.write(dev_util.READ, start=1)
    host_mem.org_addr = host_addr
    dev_mem.exp_addr = dev_addr
    simics.SIM_continue(1)
    stest.expect_equal(host_mem.org_addr, host_addr + size)
    stest.expect_equal(dev_mem.exp_addr, dev_addr + size)


class atom_add_pasid:
    # A translator that adds pasid
    cls = simics.confclass('pcie_adder')
    cls.attr.target('o')
    cls.attr.pasid('i|n', default=None)

    @cls.finalize
    def finalize(self):
        self.txl = simics.translation_t(
            target=simics.SIM_new_map_target(self.target, None, None))

    @cls.iface.transaction_translator.translate
    def translate(self, addr, access, t, callback, cbdata):
        tt = simics.transaction_t(
            prev=t, pcie_pasid=self.pasid,
            pcie_type = simics.PCIE_Type_Mem,
            pcie_at=simics.PCIE_AT_Translated,
            completion=None)
        return callback(self.txl, tt, cbdata)


pasid = 0x1234
txl0 = simics.SIM_create_object('pcie_adder', "txl0", target=ta)

mt = simics.SIM_new_map_target(ta, None, None)

msg = simics.transaction_t()
msg.pcie_type = simics.PCIE_Type_Msg
msg.pcie_error_ret = simics.pcie_error_ret_t()
msg.pcie_msg_route = simics.PCIE_Msg_Route_Upstream
msg.pcie_msg_type = simics.PCIE_PRS_Request
msg.pcie_pasid = pasid
msg.pcie_error_ret.val = simics.PCIE_Error_Not_Set
msg.pcie_prs_page_request = (UNTRANSLATED_AREA) | (0x7)
exc = simics.SIM_issue_transaction(mt, msg, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(msg.pcie_error_ret.val, simics.PCIE_Error_No_Error)

msg.pcie_prs_page_request = (UNTRANSLATED_AREA + 0x2000) | (0x7)
exc = simics.SIM_issue_transaction(mt, msg, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(msg.pcie_error_ret.val, simics.PCIE_Error_No_Error)

cmd = f"memory-map object = txl0"

# Test invalid PASID
txl0.pasid = 0xdead

info, _ = cli.quiet_run_command(cmd)
stest.expect_equal(
    info,
    []
)

# Test valid PASID
txl0.pasid = pasid

info, _ = cli.quiet_run_command(cmd)

access = simics.Sim_Access_Read | simics.Sim_Access_Write | simics.Sim_Access_Execute
stest.expect_equal(
    info,
    [
    [TRANSLATED_AREA, TRANSLATED_AREA + 0x1000 -1, "host_mem", TRANSLATED_AREA, access],
    [TRANSLATED_AREA + 0x2000, TRANSLATED_AREA + 0x3000 -1, "host_mem", TRANSLATED_AREA + 0x2000, access],
    ]
)

# Test freeing pages
msg.pcie_prs_stop_marker = True
exc = simics.SIM_issue_transaction(mt, msg, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(msg.pcie_error_ret.val, simics.PCIE_Error_No_Error)

info, _ = cli.quiet_run_command(cmd)
stest.expect_equal(
    info,
    []
)
