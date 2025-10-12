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

import ctypes

from enum import Enum


OPCODE_DELETE_IO_SUBMISSION_QUEUE = 0x00
OPCODE_CREATE_IO_SUBMISSION_QUEUE = 0x01
OPCODE_GET_LOG_PAGE = 0x02
OPCODE_CREATE_IO_COMPLETION_QUEUE = 0x05
OPCODE_ADMIN_IDENTIFY = 0x06
OPCODE_SET_FEATURES = 0x09
OPCODE_ASYNC_EVENT_REQUEST = 0x0C

OPCODE_SET_FEATURES = 0x09

CNS_NAMESPACE = 0x00
CNS_CONTROLLER = 0x01
CNS_IO_COMMAND_SET_NS = 0x05
CNS_ACTIVE_NAMESPACES_IO_SET = 0x07
CNS_NAMESPACE_IO_INDEPENDENT = 0x08

FEATURE_ARBITRATION = 0x01
FEATURE_POWER_MANAGEMENT = 0x02
FEATURE_TEMPERATURE_THRESHOLD = 0x04
FEATURE_NUMBER_OF_QUEUES = 0x07
FEATURE_INTERRUPT_COALESCING = 0x08
FEATURE_INTERRUPT_VECTOR_CONFIGURATION = 0x09
FEATURE_ASYNCHRONOUS_EVENT_CONFIGURATION = 0x0B

# IO OPC:s
OPCODE_FLUSH = 0x00
OPCODE_WRITE = 0x01
OPCODE_READ = 0x02

STATUS_TYPE_GENERIC = 0x0
STATUS_TYPE_COMMAND_SPECIFIC = 0x1

STATUS_INVALID_OPC = 0x01
STATUS_INVALID_FIELD = 0x02
STATUS_LBA_OUT_OF_RANGE = 0x80
STATUS_INVALID_LOG_PAGE = 0x09

ASYNCHRONOUS_EVENT_REQUEST_LIMIT_EXCEEDED = 0x05

LID_SUPPORTED_LOG_PAGES = 0x00
LID_ERROR_INFORMATION = 0x01
LID_SMART_HEALTH_INFORMATION = 0x02
LID_FIRMWARE_SLOT_INFORMATION = 0x03
LID_COMMANDS_SUPPORTED_AND_EFFECTS = 0x05
LID_FEATURE_IDENTIFIERS_SUPPORTED_AND_EFFECTS = 0x12
LID_NVME_MI_COMMANDS_SUPPORTED_AND_EFFECTS = 0x13


class W(ctypes.Structure):
    def as_int(self):
        return struct_to_int(self)

    @classmethod
    def from_int(cls, number: int):
        bytes = number.to_bytes(4, byteorder='little')
        return cls.from_buffer(bytearray(bytes))


class PRPEntry4(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("pba", ctypes.c_uint64, 52),
                ("offs", ctypes.c_uint64, 12)]

    def as_int(self):
        return struct_to_int(self)


class Command(ctypes.Structure):

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls.from_buffer(bytearray(data))

    def to_bytes(self):
        return bytes(self)


class CommandCompletion(Command):

    class __DW2(W):
        _pack_ = 1
        _fields_ = [("sqhd", ctypes.c_uint16),
                    ("sqid", ctypes.c_uint16)]

    class __Status(W):
        _pack_ = 1
        _fields_ = [("sc", ctypes.c_uint8),
                    ("sct", ctypes.c_uint8, 3),
                    ("crd", ctypes.c_uint8, 2),
                    ("m", ctypes.c_uint8, 1),
                    ("dnr", ctypes.c_uint8, 1)]

    class __DW3(W):
        _pack_ = 1
        _fields_ = [("cid", ctypes.c_uint16),
                    ("p", ctypes.c_uint16, 1),
                    ("status", ctypes.c_uint16, 15)]

    _pack_ = 1
    _fields_ = [("dw0", ctypes.c_uint32),
                ("dw1", ctypes.c_uint32),
                ("dw2", __DW2),
                ("dw3", __DW3)]

    def get_status(self):
        return self.__Status.from_int(self.dw3.status)

    def get_cid(self):
        return self.dw3.cid

    def get_phase(self):
        return self.dw3.p


class CommandSubmission(Command):

    class __CDW0(W):
        _pack_ = 1
        _fields_ = [("opc", ctypes.c_uint8),
                    ("psdt", ctypes.c_uint8, 2),
                    ("reserved", ctypes.c_uint8, 4),
                    ("fuse", ctypes.c_uint8, 2),
                    ("cid", ctypes.c_uint16)]

    __next_free_cid = 0

    _pack_ = 1
    _fields_ = [("cdw0", __CDW0),
                ("nsid", ctypes.c_uint32),
                ("cdw2", ctypes.c_uint32),
                ("cdw3", ctypes.c_uint32),
                ("mptr", ctypes.c_uint64),
                ("dptr_prp1", ctypes.c_uint64),
                ("dptr_prp2", ctypes.c_uint64),
                ("cdw10", ctypes.c_uint32),
                ("cdw11", ctypes.c_uint32),
                ("cdw12", ctypes.c_uint32),
                ("cdw13", ctypes.c_uint32),
                ("cdw14", ctypes.c_uint32),
                ("cdw15", ctypes.c_uint32)]

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.new_cid()

    def set_opc(self, opc):
        self.cdw0.opc = opc

    def set_nsid(self, nsid):
        self.nsid = nsid

    def set_dptr(self, prp1, prp2=0):
        self.dptr_prp1 = prp1
        self.dptr_prp2 = prp2

    def new_cid(self):
        self.cdw0.cid = CommandSubmission.__next_free_cid
        CommandSubmission.__next_free_cid += 1
        return self.cdw0.cid

    def get_opc(self):
        return self.cdw0.opc

    def get_cid(self):
        return self.cdw0.cid

    def get_nsid(self):
        return self.nsid


class IdentifyCommand(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_ADMIN_IDENTIFY)

    class __CDW10(W):
        _fields_ = [("cns", ctypes.c_uint8),
                    ("rsvd08", ctypes.c_uint8),
                    ("cntid", ctypes.c_uint16)]

    class __CDW11(W):
        _fields_ = [("csi", ctypes.c_uint8),
                    ("Reserved", ctypes.c_uint8),
                    ("cns_specific_identifier", ctypes.c_uint16)]

    def set_cdw10(self, cntid=0, cns=0):
        self.cdw10 = self.__CDW10(cns, 0, cntid).as_int()

    def set_cdw11(self, csi=0, cns_specific_identifier=0):
        self.cdw11 = self.__CDW11(csi, 0, cns_specific_identifier).as_int()


class SetFeatureNQueuesSubmission(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_SET_FEATURES)

    class __CDW10(W):
        _fields_ = [("fid", ctypes.c_uint32, 8),
                    ("rsvd08", ctypes.c_uint32, 23),
                    ("sv", ctypes.c_uint32, 1)]

    class __CDW11(W):
        _fields_ = [("nsqr", ctypes.c_uint16),
                    ("ncqr", ctypes.c_uint16)]

    def set_cdw10(self, fid):
        self.cdw10 = self.__CDW10(fid, 0, 0).as_int()

    def set_cdw11(self, n_submission_queues_wanted=0,
                  n_completion_queues_wanted=0):
        self.cdw11 = self.__CDW11(n_submission_queues_wanted,
                                  n_completion_queues_wanted).as_int()


class SetFeaturesNQueuesCompletion(CommandCompletion):
    class __DW0(W):
        _fields_ = [("nsqa", ctypes.c_uint16),
                    ("ncqa", ctypes.c_uint16)]

    def get_dw0(self):
        return self.__DW0.from_int(self.dw0)


class CreateIOCompletionQ(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_CREATE_IO_COMPLETION_QUEUE)

    class __CDW10(W):
        _fields_ = [("qsize", ctypes.c_uint16),
                    ("qid", ctypes.c_uint16)]

    class __CDW11(W):
        _fields_ = [("pc", ctypes.c_uint16, 1),
                    ("ien", ctypes.c_uint16, 1),
                    ("rsvd02", ctypes.c_uint16, 14),
                    ("iv", ctypes.c_uint16)]

    def set_cdw10(self, qid=0, qsize=1):
        if qsize == 0:
            raise ValueError("qsize must not be 0")
        self.cdw10 = self.__CDW10(qid, qsize - 1).as_int()

    def set_cdw11(self, pc=1, ien=0, iv=0):
        self.cdw11 = self.__CDW11(pc, ien, 0, iv).as_int()


class CreateIOSubmissionQ(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_CREATE_IO_SUBMISSION_QUEUE)

    class __CDW10(W):
        _fields_ = [("qsize", ctypes.c_uint16),
                    ("qid", ctypes.c_uint16)]

    class __CDW11(W):
        _fields_ = [("pc", ctypes.c_uint16, 1),
                    ("qprio", ctypes.c_uint16, 2),
                    ("rsvd03", ctypes.c_uint16, 13),
                    ("cqid", ctypes.c_uint16)]

    def set_cdw10(self, qid=0, qsize=1):
        if qsize == 0:
            raise ValueError("qsize must not be 0")
        self.cdw10 = self.__CDW10(qid, qsize - 1).as_int()

    def set_cdw11(self, pc=1, cqid=0):
        self.cdw11 = self.__CDW11(pc, 0, 0, cqid).as_int()


class DeleteIOSubmissionQ(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_DELETE_IO_SUBMISSION_QUEUE)

    class __CDW10(W):
        _fields_ = [("qid", ctypes.c_uint16),
                    ("rsvd16", ctypes.c_uint16)]

    def set_cdw10(self, qid=0):
        self.cdw10 = self.__CDW10(qid, 0).as_int()


class IO_OP(Enum):
    WRITE = 0x01
    READ = 0x02


class IORW(CommandSubmission):

    def __init__(self, op: IO_OP, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(op.value)

    class __CDW10(W):
        _fields_ = [("slba", ctypes.c_uint32)]

    class __CDW11(W):
        _fields_ = [("slba", ctypes.c_uint32)]

    class __CDW12(W):
        _fields_ = [("nlb", ctypes.c_uint16),
                    ("rsvd16", ctypes.c_uint16, 4),
                    ("dtype", ctypes.c_uint16, 1),
                    ("stc", ctypes.c_uint16, 1),
                    ("rsvd25", ctypes.c_uint16, 1),
                    ("prinfo", ctypes.c_uint16, 4),
                    ("fua", ctypes.c_uint16, 1),
                    ("lr", ctypes.c_uint16, 1)]

    def set_slba(self, slba: int):
        slba_bytes = slba.to_bytes(8, 'little')
        self.cdw10 = self.__CDW10(
            int.from_bytes(slba_bytes[:4], 'little')).as_int()
        self.cdw11 = self.__CDW11(
            int.from_bytes(slba_bytes[4:], 'little')).as_int()

    def set_cdw12(self, nlb: int):
        self.cdw12 = self.__CDW12(nlb).as_int()


class AsyncEvent(CommandCompletion):

    class __DW0(W):
        _fields_ = [("asynchronous_event_type", ctypes.c_uint8, 3),
                    ("rsvd03", ctypes.c_uint8, 5),
                    ("asynchronous_event_information", ctypes.c_uint8),
                    ("log_page_identifier", ctypes.c_uint8),
                    ("rsvd24", ctypes.c_uint8)]

    def get_dw0(self):
        return self.__DW0.from_int(self.dw0)


def struct_to_int(obj: ctypes.Structure) -> int:
    return int.from_bytes(bytearray(obj), byteorder='little')


class GetLogPage(CommandSubmission):

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.set_opc(OPCODE_GET_LOG_PAGE)

    class __CDW10(W):
        _fields_ = [("lid", ctypes.c_uint8),
                    ("lsp", ctypes.c_uint8, 7),
                    ("rae", ctypes.c_uint8, 1),
                    ("numdl", ctypes.c_uint16)]

    class __CDW11(W):
        _fields_ = [("numdu", ctypes.c_uint16),
                    ("log_specific_identifier", ctypes.c_uint16)]

    class __CDW12(W):
        _fields_ = [("lpol", ctypes.c_uint32)]

    class __CDW13(W):
        _fields_ = [("lpou", ctypes.c_uint32)]

    def set_cdw10(self, lid=0, numdl=0):
        self.cdw10 = self.__CDW10(lid, 0, 0, numdl).as_int()

    def set_cdw11(self, numdu=0):
        self.cdw11 = self.__CDW11(numdu, 0).as_int()

    def set_cdw12(self, lpol=0):
        self.cdw12 = self.__CDW12(lpol).as_int()

    def set_cdw13(self, lpou=0):
        self.cdw13 = self.__CDW11(lpou).as_int()


class Numd(W):
    _pack_ = 1
    _fields_ = [("numdl", ctypes.c_uint16),
                ("numdu", ctypes.c_uint16)]
