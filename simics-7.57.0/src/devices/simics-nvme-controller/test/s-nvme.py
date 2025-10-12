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
import ctypes
from typing import Dict, Union

import conf
import dev_util
import nvme
import stest


LB_SIZE = 512
CLOCK_FREQ_HZ = 100000000
MEGA_BYTE = 1024 * 1024
PICO = 1e12


class NVMeQueue:
    def __init__(self, base: int, size: int) -> None:
        if size == 0:
            raise ValueError("Size of NVMe queue must not be 0")
        self.base = base
        self.size = size


class NVMeSubmissionQueue(NVMeQueue):

    def __init__(self, qid: int, base: int, size: int,
                 img: simics.conf_object_t,
                 sqytdbl: dev_util.BankRegister) -> None:
        super().__init__(base, size)
        self.qid = qid
        self.sqytdbl = sqytdbl
        self.img = img
        self.tail = 0

    def write_entry(self, data: bytes):
        self.img.iface.image.set(self.base + (self.tail * 64), data)
        if self.tail == (self.size - 1):
            self.tail = 0
        else:
            self.tail += 1
        self.sqytdbl.write(SQT=self.tail)


class NVMEIOSubmissionQueue(NVMeSubmissionQueue):

    def __init__(self, qid: int, base: int, size: int, img:
                 simics.conf_object_t, sqytdbl: dev_util.BankRegister) -> None:
        super().__init__(qid, base, size, img, sqytdbl)
        self.host_write_commands = 0
        self.host_read_commands = 0

    def write_entry(self, data: bytes):
        cmd = nvme.CommandSubmission().from_bytes(data)
        opc = cmd.get_opc()
        if opc == nvme.OPCODE_WRITE:
            self.host_write_commands += 1
        elif opc == nvme.OPCODE_READ:
            self.host_read_commands += 1

        return super().write_entry(data)


class NVMeCompletionQueue(NVMeQueue):

    def __init__(self, qid: int, ien: bool, base: int, size: int,
                 img: simics.conf_object_t,
                 cqyhdbl: dev_util.BankRegister,
                 msix_data: dev_util.BankRegister) -> None:
        super().__init__(base, size)
        self.qid = qid
        self.ien = ien
        self.cqyhdbl = cqyhdbl
        self.img = img
        self.msix_data = msix_data
        self.head = 0
        self.old_phase = 0
        self.n_errors = 0

    def __check_phase(self) -> bool:
        data = self.img.iface.image.get(self.base + (self.head * 16), 16)
        data = nvme.CommandCompletion.from_bytes(data)
        return data.dw3.p != self.old_phase

    def __check_if_error(self, data: bytes):
        rsp = nvme.CommandCompletion.from_bytes(data)
        if rsp.get_status().sc != 0:
            self.n_errors += 1

    def read_entry(self, expected_steps=1):
        simics.SIM_continue(expected_steps)
        if not self.__check_phase():
            raise RuntimeError(f'No unread entry in queue {self.qid}')

        if self.ien:
            stest.expect_equal(self.validate_msix_status(), True)

        data = self.img.iface.image.get(self.base + (self.head * 16), 16)
        if self.head == (self.size - 1):
            self.head = 0
            self.old_phase = 1 if (self.old_phase == 0) else 0
        else:
            self.head += 1
        self.cqyhdbl.write(self.head)

        self.__check_if_error(data)
        return data

    def validate_msix_status(self) -> bool:
        pending = self.msix_data.pending[int(self.qid / 32)].read()
        if ((1 << (self.qid % 32)) & pending) != 0:
            self.msix_data.pending[int(self.qid / 32)].write(0)
            return True
        return False


class NVMeDevice:

    def __init__(self, namespace_sizes: list[int] = [], disk_size: int = 0,
                 upstream_mem_size: int = 0x20000) -> None:
        images = []
        clock = simics.pre_conf_object('clock', 'clock')
        clock.freq_mhz = CLOCK_FREQ_HZ / 1000000
        for ns_size in namespace_sizes:
            images.append(simics.pre_conf_object(None, 'image', size=ns_size))
        nvme = simics.pre_conf_object('nvme0', 'simics_nvme_controller',
                                      disk_size=disk_size,
                                      namespace_sizes=namespace_sizes,
                                      images=images)
        test_dp = simics.pre_conf_object('test_dp', 'pcie-downstream-port')
        img = simics.pre_conf_object('test_image', 'image',
                                     size=upstream_mem_size)
        ram = simics.pre_conf_object('test_ram', 'ram', image=img)
        test_dp.upstream_target = ram

        nvme.queue = clock
        test_dp.queue = clock
        for image in images:
            simics.SIM_add_configuration([image], None)
        simics.SIM_add_configuration([nvme, clock, test_dp, img, ram], None)

        self.dev_obj = conf.nvme0
        self.dp = conf.test_dp
        self.img = conf.test_image
        self.dp.devices = [[0, self.dev_obj]]
        self.ram = conf.test_ram
        self.clock = conf.clock

        self.__all_qs: list[NVMeQueue] = []
        self.__sqs: Dict[int, NVMeSubmissionQueue] = {}
        self.__cqs: Dict[int, NVMeCompletionQueue] = {}

        self.pcie_config = dev_util.bank_regs(self.dev_obj.bank.pcie_config)
        self.msix_data = dev_util.bank_regs(self.dev_obj.bank.msix_data)
        self.properties = dev_util.bank_regs(self.dev_obj.bank.properties)

        self.cmd_buffer_memory_base = 0

    def configure_admin_queues(self, base, n_entries):
        asq = align(base, 4096)
        acq = align(n_entries * ctypes.sizeof(nvme.CommandSubmission), 4096)

        if (asq * 10) > (0x20000 / 2):
            raise ValueError(
                "Select a lower base for admin queues or less entries")
        self.cmd_buffer_memory_base = acq * 10

        self.__sqs[0] = NVMeSubmissionQueue(
            0, asq, n_entries, self.img, self.properties.doorbells[0].SQyTDBL)
        self.__cqs[0] = NVMeCompletionQueue(
            0, True, acq, n_entries, self.img,
            self.properties.doorbells[0].CQyHDBL, self.msix_data)

        self.__all_qs.append(self.__sqs[0])
        self.__all_qs.append(self.__cqs[0])

    def write_upstream_ram(self, addr: int, data: bytes):
        self.img.iface.image.set(addr, data)

    def read_upstream_ram(self, addr: int, size: int) -> bytes:
        return self.img.iface.image.get(addr, size)

    def get_sq(self, qid: int) -> NVMeSubmissionQueue:
        return self.__sqs[qid]

    def get_cq(self, qid: int) -> NVMeCompletionQueue:
        return self.__cqs[qid]

    def add_io_sq(self, qid: int, size: int):
        if len(self.__sqs) == 0:
            raise RuntimeError(
                "configure_admin_queues() must be called before adding io"
                " queues")
        if qid == 0:
            raise ValueError("IO queue must not have qid 0")
        if self.__sqs.get(qid) is not None:
            raise ValueError("qid already exists")
        prev_q_base = self.__all_qs[-1].base
        prev_q_size = self.__all_qs[-1].size
        base = align(prev_q_base + 64 * prev_q_size, 4096)
        new_q = NVMEIOSubmissionQueue(qid, base, size, self.img,
                                      self.properties.doorbells[qid].SQyTDBL)
        self.__all_qs.append(new_q)
        self.__sqs[qid] = new_q

    def del_io_sq(self, qid: int):
        for i, q in enumerate(self.__all_qs):
            if q.qid == qid and type(q) is NVMeSubmissionQueue:
                del self.__all_qs[i]
        del self.__sqs[qid]

    def add_io_cq(self, qid: int, ien: bool, size: int):
        if len(self.__cqs) == 0:
            raise RuntimeError(
                "configure_admin_queues() must be called before adding io"
                " queues")
        if qid == 0:
            raise ValueError("IO queue must not have qid 0")
        if self.__cqs.get(qid) is not None:
            raise ValueError("qid already exists")
        prev_q_base = self.__all_qs[-1].base
        prev_q_size = self.__all_qs[-1].size
        base = align(prev_q_base + 64 * prev_q_size, 4096)
        new_q = NVMeCompletionQueue(qid, ien, base, size, self.img,
                                    self.properties.doorbells[qid].CQyHDBL,
                                    self.msix_data)
        self.__all_qs.append(new_q)
        self.__cqs[qid] = new_q

    def get_n_errors(self) -> int:
        n_errors = 0
        for q in self.__cqs.values():
            n_errors += q.n_errors
        return n_errors

    def get_n_write_cmds(self) -> int:
        n_write_cmds = 0
        for q in self.__sqs.values():
            if isinstance(q, NVMEIOSubmissionQueue):
                n_write_cmds += q.host_write_commands
        return n_write_cmds

    def get_n_read_cmds(self) -> int:
        n_read_cmds = 0
        for q in self.__sqs.values():
            if isinstance(q, NVMEIOSubmissionQueue):
                n_read_cmds += q.host_read_commands
        return n_read_cmds

    # Calculates the same amount of cycles as a call to post_cycles would use
    def cycles_delta(self, seconds: float) -> int:
        ps = int((seconds * PICO) + 0.5)
        r = ((ps * CLOCK_FREQ_HZ) + (PICO / 2)) / PICO
        return int(r)


def identify_controller(dev: NVMeDevice):
    cmd_rsp_buffer_addr = dev.cmd_buffer_memory_base

    id_ctrl_cmd = nvme.IdentifyCommand()
    id_ctrl_cmd.set_dptr(nvme.PRPEntry4(cmd_rsp_buffer_addr, 0).as_int())
    id_ctrl_cmd.set_cdw10(cns=nvme.CNS_CONTROLLER)

    dev.get_sq(0).write_entry(id_ctrl_cmd.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    # Command buffer response
    rsp = dev.read_upstream_ram(cmd_rsp_buffer_addr, 4096)
    # Vendor id
    stest.expect_equal(int.from_bytes(rsp[0:3], byteorder='little'), 0x8086)
    # Controller type
    stest.expect_equal(rsp[111], 1)


def identify_command_sets(dev: NVMeDevice):
    cmd_rsp_buffer_addr = dev.cmd_buffer_memory_base

    id_active_namespaces = nvme.IdentifyCommand()
    id_active_namespaces.set_dptr(
        nvme.PRPEntry4(cmd_rsp_buffer_addr, 0).as_int())
    id_active_namespaces.set_cdw10(cns=nvme.CNS_ACTIVE_NAMESPACES_IO_SET)

    dev.get_sq(0).write_entry(id_active_namespaces.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    # Command buffer response
    rsp = dev.read_upstream_ram(cmd_rsp_buffer_addr, 4096)
    stest.expect_equal(int.from_bytes(rsp[0:3], byteorder='little'), 1)
    stest.expect_equal(rsp[1:4096], bytes(4095))


def identify_namespace(dev: NVMeDevice):
    cmd_rsp_buffer_addr = dev.cmd_buffer_memory_base

    id_namespaces = nvme.IdentifyCommand(nsid=1)
    id_namespaces.set_dptr(
        nvme.PRPEntry4(cmd_rsp_buffer_addr, 0).as_int())
    id_namespaces.set_cdw10(cns=nvme.CNS_NAMESPACE)

    dev.get_sq(0).write_entry(id_namespaces.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    # Command buffer response
    rsp = dev.read_upstream_ram(cmd_rsp_buffer_addr, 4096)
    nsze = int.from_bytes(rsp[0:8], byteorder='little')
    ncap = int.from_bytes(rsp[8:16], byteorder='little')
    nuse = int.from_bytes(rsp[16:24], byteorder='little')
    lbaf0 = rsp[128 + 2]
    stest.expect_equal(nsze, 0x1000000 / 512)
    stest.expect_equal(ncap, nsze)
    stest.expect_equal(nuse, ncap)
    stest.expect_equal(lbaf0, 9)
    stest.expect_equal(rsp[384:4096], bytes(3712))


def identify_io_command_set_namespace(dev: NVMeDevice):
    cmd_rsp_buffer_addr = dev.cmd_buffer_memory_base

    id_io_namespaces = nvme.IdentifyCommand(nsid=1)
    id_io_namespaces.set_dptr(
        nvme.PRPEntry4(cmd_rsp_buffer_addr, 0).as_int())
    id_io_namespaces.set_cdw10(cns=nvme.CNS_NAMESPACE_IO_INDEPENDENT)

    dev.get_sq(0).write_entry(id_io_namespaces.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    # Command buffer response
    rsp = dev.read_upstream_ram(cmd_rsp_buffer_addr, 4096)
    stest.expect_equal(rsp[14], 1)
    stest.expect_equal(rsp[15:4096], bytes(4081))


def determine_io_queues(dev: NVMeDevice):
    cmd_rsp_buffer_addr = dev.cmd_buffer_memory_base

    cmd_set_feature_n_qs = nvme.SetFeatureNQueuesSubmission()
    cmd_set_feature_n_qs.set_dptr(
        nvme.PRPEntry4(cmd_rsp_buffer_addr, 0).as_int())
    cmd_set_feature_n_qs.set_cdw10(fid=nvme.FEATURE_NUMBER_OF_QUEUES)
    cmd_set_feature_n_qs.set_cdw11(2, 2)

    dev.get_sq(0).write_entry(cmd_set_feature_n_qs.to_bytes())

    completion_entry = nvme.SetFeaturesNQueuesCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)
    stest.expect_true(completion_entry.get_dw0().nsqa >= 2)
    stest.expect_true(completion_entry.get_dw0().ncqa >= 2)


def configure_msix(dev: NVMeDevice):
    dev.pcie_config.msix.control.write(dev_util.READ, enable=1)
    dev.pcie_config.msix.control.write(dev_util.READ, mask=1)


def create_io_completion_queue(dev: NVMeDevice, qid: int):
    qsize = 8
    dev.add_io_cq(qid, True, qsize)

    cmd_create_io_cqs = nvme.CreateIOCompletionQ()
    cmd_create_io_cqs.set_dptr(dev.get_cq(qid).base)
    cmd_create_io_cqs.set_cdw10(qid=qid, qsize=qsize)
    cmd_create_io_cqs.set_cdw11(ien=1, iv=qid)
    dev.get_sq(0).write_entry(cmd_create_io_cqs.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)


def create_io_submission_queue(dev: NVMeDevice, qid: int, cqid=0):
    qsize = 8
    dev.add_io_sq(qid, qsize)

    cmd_create_io_sqs = nvme.CreateIOSubmissionQ()
    cmd_create_io_sqs.set_dptr(dev.get_sq(qid).base)
    cmd_create_io_sqs.set_cdw10(qid=qid, qsize=qsize)
    cmd_create_io_sqs.set_cdw11(cqid=cqid if cqid != 0 else qid)
    dev.get_sq(0).write_entry(cmd_create_io_sqs.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)


def provide_async_event_slot(dev):
    cmd_async_event = nvme.CommandSubmission()
    cmd_async_event.set_opc(nvme.OPCODE_ASYNC_EVENT_REQUEST)
    dev.get_sq(0).write_entry(cmd_async_event.to_bytes())


def provide_async_event_slots(dev):
    for _ in range(4):
        # Give async event slot to dev
        provide_async_event_slot(dev)
        # Ensure that there is no response to the above command at this point
        with stest.expect_exception_mgr(RuntimeError):
            dev.get_cq(0).read_entry()

    # Try to give a fifth slot with only 4 slots available in device (id.aerl)
    provide_async_event_slot(dev)
    with stest.expect_log_mgr(
        log_type='error', regex="The number of concurrently outstanding "
            "Asynchronous Event Request commands has been exceeded"):
        completion_entry = nvme.CommandCompletion.from_bytes(
            dev.get_cq(0).read_entry())

    stest.expect_equal(completion_entry.get_status().sct,
                       nvme.STATUS_TYPE_COMMAND_SPECIFIC)
    stest.expect_equal(completion_entry.get_status().sc,
                       nvme.ASYNCHRONOUS_EVENT_REQUEST_LIMIT_EXCEEDED)


def init_test(dev: NVMeDevice):
    dev.pcie_config.command.write(dev_util.READ, m=1)
    dev.pcie_config.msix.control.write(dev_util.READ, enable=1)
    dev.pcie_config.msix.control.write(dev_util.READ, mask=1)

    stest.expect_equal(dev.properties.CSTS.field.RDY.read(), 0)
    max_queue_size = dev.properties.CAP.field.MQES.read()
    stest.expect_true(max_queue_size <= 4096 and max_queue_size > 0)
    stest.expect_true(max_queue_size > 8)

    # Set admin queue submission and completion queue sizes
    dev.properties.AQA.write(ACQS=(8 - 1), ASQS=(8 - 1))
    dev.configure_admin_queues(0, 8)
    dev.properties.ASQ.write(dev.get_sq(0).base)
    dev.properties.ACQ.write(dev.get_cq(0).base)

    stest.expect_equal(dev.properties.CAP.field.CSS.read(), 0b00000001)

    dev.properties.CC.write(CSS=0x00, AMS=0, MPS=0, EN=1, CRIME=0, IOCQES=0,
                            IOSQES=0, SHN=0)

    stest.expect_equal(dev.properties.CSTS.field.RDY.read(), 1)

    identify_controller(dev)
    identify_command_sets(dev)
    identify_namespace(dev)
    identify_io_command_set_namespace(dev)
    determine_io_queues(dev)
    configure_msix(dev)
    create_io_completion_queue(dev, 1)
    create_io_submission_queue(dev, 1)
    provide_async_event_slots(dev)


def io_write(dev: NVMeDevice):
    write_buffer = dev.cmd_buffer_memory_base

    cmd_read = nvme.IORW(nvme.IO_OP.WRITE)
    cmd_read.set_dptr(
        nvme.PRPEntry4(write_buffer, 0).as_int())
    cmd_read.set_slba(0)
    cmd_read.set_cdw12(0)
    cmd_read.set_nsid(1)
    dev.write_upstream_ram(write_buffer, 0x1234.to_bytes(512, 'little'))
    dev.get_sq(1).write_entry(cmd_read.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(1).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)


def io_read(dev: NVMeDevice):
    read_buffer = dev.cmd_buffer_memory_base

    cmd_write = nvme.IORW(nvme.IO_OP.READ)
    cmd_write.set_dptr(
        nvme.PRPEntry4(read_buffer, 0).as_int())
    cmd_write.set_slba(0)
    cmd_write.set_cdw12(0)
    cmd_write.set_nsid(1)
    dev.get_sq(1).write_entry(cmd_write.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(1).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    data = dev.read_upstream_ram(read_buffer, 2)
    stest.expect_equal(int.from_bytes(data, 'little'), 0x1234)


def io_tests(dev: NVMeDevice):
    io_write(dev)
    io_read(dev)


def invalid_opc(dev: NVMeDevice):
    cmd_invalid_opc = nvme.CommandSubmission()
    cmd_invalid_opc.set_opc(0xA0)
    with stest.expect_log_mgr(
            log_type='unimpl',
            regex=f"Invalid or unimplemented admin OPC {0xA0}"):
        dev.get_sq(0).write_entry(cmd_invalid_opc.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(
        completion_entry.get_status().sct, nvme.STATUS_TYPE_GENERIC)
    stest.expect_equal(
        completion_entry.get_status().sc, nvme.STATUS_INVALID_OPC)


def invalid_nsid(dev: NVMeDevice):
    cmd_write_invalid_nsid = nvme.CommandSubmission()
    cmd_write_invalid_nsid.set_opc(nvme.OPCODE_WRITE)
    cmd_write_invalid_nsid.set_nsid(123)
    with stest.expect_log_mgr(
        log_type='error',
            regex="Inactive NSID in WRITE command"):
        dev.get_sq(1).write_entry(cmd_write_invalid_nsid.to_bytes())
        completion_entry = nvme.CommandCompletion.from_bytes(
            dev.get_cq(1).read_entry())

    stest.expect_equal(
        completion_entry.get_status().sct, nvme.STATUS_TYPE_GENERIC)
    stest.expect_equal(
        completion_entry.get_status().sc, nvme.STATUS_INVALID_FIELD)


def invalid_io_lb_range(dev: NVMeDevice):
    write_buffer = dev.cmd_buffer_memory_base

    cmd_read = nvme.IORW(nvme.IO_OP.WRITE)
    cmd_read.set_dptr(
        nvme.PRPEntry4(write_buffer, 0).as_int())
    cmd_read.set_slba(99999999)
    cmd_read.set_cdw12(0)
    cmd_read.set_nsid(1)
    dev.write_upstream_ram(write_buffer, 0x1234.to_bytes(512, 'little'))
    with stest.expect_log_mgr(log_type='error', regex='Invalid LBA range'):
        dev.get_sq(1).write_entry(cmd_read.to_bytes())
        completion_entry = nvme.CommandCompletion.from_bytes(
            dev.get_cq(1).read_entry())

    stest.expect_equal(
        completion_entry.get_status().sct, nvme.STATUS_TYPE_GENERIC)
    stest.expect_equal(
        completion_entry.get_status().sc, nvme.STATUS_LBA_OUT_OF_RANGE)


def bad_doorbell_async_event(dev: NVMeDevice, sq_id: int):
    with stest.expect_log_mgr(
            log_type='error',
            regex=f'Write to invalid doorbell register SQ{sq_id}TDBL'):
        dev.properties.doorbells[sq_id].SQyTDBL.write(SQT=1)

    # Ensure async event is returned in admin queue
    completion_entry = nvme.AsyncEvent.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)
    stest.expect_equal(completion_entry.get_dw0().asynchronous_event_type, 0)
    stest.expect_equal(
        completion_entry.get_dw0().asynchronous_event_information, 0)

    # Replace the consumed async event slot (should not be full now)
    with stest.expect_exception_mgr(RuntimeError):
        provide_async_event_slot(dev)
        dev.get_cq(0).read_entry()

    # And now full again
    with stest.expect_log_mgr(
        log_type='error', regex="The number of concurrently outstanding "
            "Asynchronous Event Request commands has been exceeded"):
        provide_async_event_slot(dev)
        dev.get_cq(0).read_entry()


def bad_requests(dev: NVMeDevice):
    invalid_opc(dev)
    invalid_nsid(dev)
    invalid_io_lb_range(dev)


def queue_wrap_head(dev: NVMeDevice):
    acq = dev.get_cq(0)
    asq = dev.get_sq(0)

    with stest.allow_log_mgr():
        cmd = nvme.CommandSubmission().from_bytes(bytes(64))
        asq.write_entry(cmd.to_bytes())
    cmd_cmpl = nvme.CommandCompletion.from_bytes(acq.read_entry())
    initial_phase = cmd_cmpl.dw3.p
    initial_sqhd = cmd_cmpl.dw2.sqhd

    phase_changed = False
    sqhd_tracker = initial_sqhd
    for _ in range(acq.size + 1):
        with stest.allow_log_mgr():
            cmd = nvme.CommandSubmission().from_bytes(bytes(64))
            asq.write_entry(cmd.to_bytes())
        cmd_cmpl = nvme.CommandCompletion.from_bytes(acq.read_entry())
        if cmd_cmpl.dw3.p != initial_phase:
            phase_changed = True

        if sqhd_tracker == (acq.size - 1):
            sqhd_tracker = 0
        else:
            sqhd_tracker += 1

    stest.expect_true(phase_changed)
    stest.expect_equal(cmd_cmpl.dw2.sqhd, sqhd_tracker)


def bandwidth(dev: NVMeDevice):
    initial_bw = dev.dev_obj.bandwidth
    read_write_buffer = dev.cmd_buffer_memory_base

    dev.dev_obj.bandwidth = 1
    nlb = 22
    data_len = LB_SIZE * nlb

    cmd_io = nvme.IORW(nvme.IO_OP.WRITE)
    cmd_io.set_dptr(
        nvme.PRPEntry4(read_write_buffer, 0).as_int())
    cmd_io.set_slba(0)
    cmd_io.set_cdw12(nlb-1)
    cmd_io.set_nsid(1)

    dev.write_upstream_ram(read_write_buffer, bytes(data_len))
    dev.get_sq(1).write_entry(cmd_io.to_bytes())

    expected_time = data_len / (dev.dev_obj.bandwidth * MEGA_BYTE)
    expected_steps = dev.cycles_delta(expected_time)

    with stest.expect_exception_mgr(RuntimeError):
        dev.get_cq(1).read_entry(expected_steps-1)
    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(1).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    dev.dev_obj.bandwidth = 250
    nlb = 33
    data_len = LB_SIZE * nlb
    cmd_io.new_cid()
    cmd_io.set_opc(nvme.OPCODE_READ)
    cmd_io.set_cdw12(nlb-1)
    dev.write_upstream_ram(read_write_buffer, bytes(data_len))
    dev.get_sq(1).write_entry(cmd_io.to_bytes())

    expected_time = data_len / (dev.dev_obj.bandwidth * MEGA_BYTE)
    expected_steps = dev.cycles_delta(expected_time)

    with stest.expect_exception_mgr(RuntimeError):
        dev.get_cq(1).read_entry(expected_steps-1)
    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(1).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    dev.dev_obj.bandwidth = initial_bw


def arbitration(dev: NVMeDevice):
    create_io_submission_queue(dev, 2, 1)
    initial_bw = dev.dev_obj.bandwidth
    read_write_buffer = dev.cmd_buffer_memory_base

    dev.dev_obj.bandwidth = 1
    nlb = 1
    data_len = LB_SIZE * nlb
    cids_sq1 = []
    cids_sq2 = []

    expected_time = data_len / (dev.dev_obj.bandwidth * MEGA_BYTE)
    expected_steps = dev.cycles_delta(expected_time)

    cmd_io = nvme.IORW(nvme.IO_OP.WRITE)
    cmd_io.set_dptr(
        nvme.PRPEntry4(read_write_buffer, 0).as_int())
    cmd_io.set_slba(0)
    cmd_io.set_cdw12(nlb-1)
    cmd_io.set_nsid(1)
    dev.write_upstream_ram(read_write_buffer, bytes(data_len))
    for _ in range(2):
        cids_sq1.append(cmd_io.new_cid())
        dev.get_sq(1).write_entry(cmd_io.to_bytes())
    for _ in range(2):
        cids_sq2.append(cmd_io.new_cid())
        dev.get_sq(2).write_entry(cmd_io.to_bytes())

    cids_expected_order = [cids_sq1[0], cids_sq2[0], cids_sq1[1], cids_sq2[1]]
    cids_actual_order = []
    for i in range(4):
        rsp = nvme.CommandCompletion.from_bytes(
            dev.get_cq(1).read_entry(expected_steps))
        cids_actual_order.append(rsp.get_cid())
        with stest.expect_exception_mgr(RuntimeError):
            dev.get_cq(1).read_entry()
    stest.expect_equal(cids_actual_order, cids_expected_order)

    dev.dev_obj.bandwidth = initial_bw


def delete_queue(dev: NVMeDevice):
    qid = 2
    dev.del_io_sq(qid)
    cmd_delete_io_sq = nvme.DeleteIOSubmissionQ()
    cmd_delete_io_sq.set_cdw10(qid=qid)
    dev.get_sq(0).write_entry(cmd_delete_io_sq.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())
    stest.expect_equal(completion_entry.dw3.status, 0)

    bad_doorbell_async_event(dev, 2)

def reset_queue(dev: NVMeDevice):
    with stest.expect_log_mgr(log_type="info", regex="Resetting all NVMe queues"):
        dev.properties.CC.write(0)
    with stest.expect_exception_mgr(stest.TestFailure):
        with stest.expect_log_mgr(log_type="info", regex="Resetting all NVMe queues"):
            dev.properties.CC.write(0)


def read_log_page(dev: NVMeDevice, lid: int, size: int):
    write_buffer = dev.cmd_buffer_memory_base
    numd = nvme.Numd().from_int(int(size / 4) - 1)

    cmd = nvme.GetLogPage()
    cmd.set_dptr(nvme.PRPEntry4(write_buffer, 0).as_int())
    cmd.set_cdw10(lid, numd.numdl)
    cmd.set_cdw11(numd.numdu)
    dev.get_sq(0).write_entry(cmd.to_bytes())

    completion_entry = nvme.CommandCompletion.from_bytes(
        dev.get_cq(0).read_entry())

    # Log page
    page = dev.read_upstream_ram(write_buffer, size)

    return page, completion_entry


def log_page_smart_health(dev: NVMeDevice):
    page, completion_entry = read_log_page(
        dev, nvme.LID_SMART_HEALTH_INFORMATION, 512)
    stest.expect_equal(completion_entry.dw3.status, 0)

    number_of_error_information_log_entries = int.from_bytes(
        page[176:191], byteorder='little')
    host_write_commands = int.from_bytes(page[80:95], byteorder='little')
    host_read_commands = int.from_bytes(page[64:79], byteorder='little')

    stest.expect_equal(number_of_error_information_log_entries,
                       dev.get_n_errors())
    stest.expect_equal(host_write_commands, dev.get_n_write_cmds())
    stest.expect_equal(host_read_commands, dev.get_n_read_cmds())


def log_page_error_info(dev: NVMeDevice):
    # Bad request
    cmd = nvme.CommandSubmission()
    cmd.set_opc(12345)
    cmd.set_nsid(1)
    with stest.expect_log_mgr(log_type='unimpl'):
        dev.get_sq(1).write_entry(cmd.to_bytes())
    rsp = nvme.CommandCompletion.from_bytes(dev.get_cq(1).read_entry())

    page, completion_entry = read_log_page(dev, nvme.LID_ERROR_INFORMATION, 64)
    stest.expect_equal(completion_entry.dw3.status, 0)

    error_count = int.from_bytes(page[0:7], byteorder='little')
    sqid = int.from_bytes(page[8:9], byteorder='little')
    cid = int.from_bytes(page[10:11], byteorder='little')
    status_p = int.from_bytes(page[12:13], byteorder='little')
    parameter_error_location = int.from_bytes(page[14:15], byteorder='little')
    nsid = int.from_bytes(page[24:27], byteorder='little')

    stest.expect_equal(error_count, dev.get_n_errors())
    stest.expect_equal(sqid, 1)
    stest.expect_equal(cid, cmd.get_cid())
    stest.expect_equal(get_bits(status_p, 16, 0, 1), rsp.get_phase())
    stest.expect_equal(
        get_bits(status_p, 16, 1, 15), rsp.get_status().as_int())
    stest.expect_equal(get_bits(parameter_error_location, 16, 0, 8), 0)
    stest.expect_equal(get_bits(parameter_error_location, 16, 8, 3), 0)
    stest.expect_equal(nsid, cmd.get_nsid())


def check_feature(supported_features_page: bytes, fid: int,
                  should_be_supported: bool):
    start = fid * 4
    end = start + 3
    fid_supported = int.from_bytes(
        supported_features_page[start:end], byteorder='little')
    if should_be_supported:
        stest.expect_equal(get_bits(fid_supported, 32, 0, 1), 1)
    else:
        stest.expect_equal(get_bits(fid_supported, 32, 0, 1), 0)


def log_page_supported_features(dev: NVMeDevice):
    page, completion_entry = read_log_page(
        dev, nvme.LID_FEATURE_IDENTIFIERS_SUPPORTED_AND_EFFECTS, 1024)
    stest.expect_equal(completion_entry.dw3.status, 0)

    check_feature(page, nvme.FEATURE_ARBITRATION, True)
    check_feature(page, nvme.FEATURE_POWER_MANAGEMENT, True)
    check_feature(page, nvme.FEATURE_TEMPERATURE_THRESHOLD, True)
    check_feature(page, nvme.FEATURE_NUMBER_OF_QUEUES, True)
    check_feature(page, nvme.FEATURE_INTERRUPT_COALESCING, True)
    check_feature(page, nvme.FEATURE_INTERRUPT_VECTOR_CONFIGURATION, True)
    check_feature(page, nvme.FEATURE_ASYNCHRONOUS_EVENT_CONFIGURATION, True)

    unsupported_feature = 0xA0
    check_feature(page, unsupported_feature, False)


def check_cmd(supported_commands_page: bytes, opc: int,
              should_be_supported: bool, io_cmd=False):
    start = opc * 4
    if io_cmd:
        start += 1024
    end = start + 3
    cmd_supported = int.from_bytes(
        supported_commands_page[start:end], byteorder='little')
    if should_be_supported:
        stest.expect_equal(get_bits(cmd_supported, 32, 0, 1), 1)
    else:
        stest.expect_equal(get_bits(cmd_supported, 32, 0, 1), 0)


def log_page_supported_commands(dev: NVMeDevice):
    page, completion_entry = read_log_page(
        dev, nvme.LID_COMMANDS_SUPPORTED_AND_EFFECTS, 4096)
    stest.expect_equal(completion_entry.dw3.status, 0)

    check_cmd(page, nvme.OPCODE_DELETE_IO_SUBMISSION_QUEUE, True)
    check_cmd(page, nvme.OPCODE_CREATE_IO_SUBMISSION_QUEUE, True)
    check_cmd(page, nvme.OPCODE_GET_LOG_PAGE, True)
    check_cmd(page, nvme.OPCODE_CREATE_IO_COMPLETION_QUEUE, True)
    check_cmd(page, nvme.OPCODE_ADMIN_IDENTIFY, True)
    check_cmd(page, nvme.OPCODE_SET_FEATURES, True)
    check_cmd(page, nvme.OPCODE_ASYNC_EVENT_REQUEST, True)

    check_cmd(page, nvme.OPCODE_WRITE, True, True)
    check_cmd(page, nvme.OPCODE_READ, True, True)
    check_cmd(page, nvme.OPCODE_FLUSH, True, True)

    unsupported_cmd = 0xA0
    check_feature(page, unsupported_cmd, False)


def check_log_page(supported_commands_page: bytes, lid: int,
                   should_be_supported: bool):
    start = lid * 4
    end = start + 3
    lp_supported = int.from_bytes(
        supported_commands_page[start:end], byteorder='little')
    if should_be_supported:
        stest.expect_equal(get_bits(lp_supported, 32, 0, 1), 1)
    else:
        stest.expect_equal(get_bits(lp_supported, 32, 0, 1), 0)


def log_page_supported_log_pages(dev: NVMeDevice):
    page, completion_entry = read_log_page(
        dev, nvme.LID_SUPPORTED_LOG_PAGES, 1024)
    stest.expect_equal(completion_entry.dw3.status, 0)

    check_cmd(page, nvme.LID_SUPPORTED_LOG_PAGES, True)
    check_cmd(page, nvme.LID_ERROR_INFORMATION, True)
    check_cmd(page, nvme.LID_SMART_HEALTH_INFORMATION, True)
    check_cmd(page, nvme.LID_FIRMWARE_SLOT_INFORMATION, True)
    check_cmd(page, nvme.LID_COMMANDS_SUPPORTED_AND_EFFECTS, True)
    check_cmd(page, nvme.LID_FEATURE_IDENTIFIERS_SUPPORTED_AND_EFFECTS, True)
    check_cmd(page, nvme.LID_NVME_MI_COMMANDS_SUPPORTED_AND_EFFECTS, True)

    unsupported_log_page = 0xA0
    check_feature(page, unsupported_log_page, False)


def bad_lid(dev: NVMeDevice):
    with stest.expect_log_mgr(
        log_type="info",
        regex="NVMe host trying to access unimplemented log page"
            + f" with LID {0xA0}"):
        _, completion_entry = read_log_page(dev, 0xA0, 64)

    stest.expect_equal(
        completion_entry.get_status().sc, nvme.STATUS_INVALID_LOG_PAGE)
    stest.expect_equal(
        completion_entry.get_status().sct, nvme.STATUS_TYPE_COMMAND_SPECIFIC)


def log_pages(dev: NVMeDevice):
    log_page_smart_health(dev)
    log_page_error_info(dev)
    log_page_supported_features(dev)
    log_page_supported_commands(dev)
    log_page_supported_log_pages(dev)
    bad_lid(dev)


def create_nvme_pcie_device(namespace_sizes: list[int] = [],
                            disk_size: int = 0) -> NVMeDevice:
    '''Create a new NVMe PCIe Device'''
    return NVMeDevice(namespace_sizes, disk_size)


def align(offset, align):
    return (offset + (align - 1)) & -align


def get_bits(number: int, width: int, off: int, n_bits: int):
    b = bin(number)[2:]
    if (width - len(b)) > 0:
        b = '0' * (width - len(b)) + b

    end = len(b) - off
    start = end - n_bits

    return int(b[start:end], 2)


def bad_namespaces():
    ns1_size = 1024
    ns2_size = 2048
    img1 = simics.pre_conf_object(None, 'image', size=ns1_size)

    clock = simics.pre_conf_object('clock', 'clock')
    clock.freq_mhz = CLOCK_FREQ_HZ / 1000000
    nvme1 = simics.pre_conf_object('nvme1', 'simics_nvme_controller',
                                   disk_size=(ns1_size + ns2_size),
                                   namespace_sizes=[ns1_size, ns2_size],
                                   images=[img1])
    with stest.expect_log_mgr(
        regex=(r"The number of provided namespace images \(1\) is not equal to"
               + r" the number of provided namespace sizes \(2\).")):
        simics.SIM_add_configuration([nvme1, img1], None)

    img2 = simics.pre_conf_object(None, 'image', size=ns2_size)
    nvme2 = simics.pre_conf_object('nvme2', 'simics_nvme_controller',
                                   disk_size=(ns1_size + ns2_size - 1),
                                   namespace_sizes=[ns1_size, ns2_size],
                                   images=[img1, img2])
    with stest.expect_log_mgr(
        msg=(f"Sum of namespace sizes ({ns1_size + ns2_size}) is largesr than"
             f"the total size of the disk ({ns1_size + ns2_size - 1})")):
        simics.SIM_add_configuration([nvme2, img2], None)


def main():
    nvme_dev = create_nvme_pcie_device([0x1000000], 0x1000000)
    nvme_dev.dev_obj.log_level = 4

    bad_namespaces()

    init_test(nvme_dev)
    io_tests(nvme_dev)
    bad_requests(nvme_dev)
    bad_doorbell_async_event(nvme_dev, 4)
    queue_wrap_head(nvme_dev)
    bandwidth(nvme_dev)
    arbitration(nvme_dev)
    log_pages(nvme_dev)

    # These test case should be last
    delete_queue(nvme_dev)
    reset_queue(nvme_dev)


main()
