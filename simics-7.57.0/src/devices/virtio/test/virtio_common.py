# © 2020 Intel Corporation
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

import struct
import types
from typing import Callable, Dict, List, Optional, Tuple, TypeVar

import conf
# SIMICS-20543
conf.sim.deprecation_level = 0

TVirtioDevicePCIE = TypeVar("TVirtioDevicePCIE")
TVirtioPCIEVirtualFunction = TypeVar("TVirtioPCIEVirtualFunction")
avail_header_len = 4
used_header_len = 4

page_size = 4096

VIRTQ_DESC_F_NEXT = 0x1
VIRTQ_DESC_F_WRITE = 0x2

VIRTIO_MSI_NO_VECTOR = 0xFFFF

VIRTIO_F_VERSION_1 = 32
VIRTIO_F_ACCESS_PLATFORM = 33
VIRTIO_F_SR_IOV = 37

N_FEATURE_REGS = 4


class VirtQueueMem:
    def __init__(self, queue_size):
        self.qsz = queue_size

        def align(x):
            return (x + (page_size-1)) & ~(page_size-1)

        # sizeof(virtq_desc_t) == 16
        # sizeof(virtq_used_elem_t) == 8
        self.avail_offs = 16*self.qsz
        avail_size = 2*(3 + self.qsz)
        self.used_offs = align(self.avail_offs + avail_size)
        used_size = 2*3 + 8*self.qsz

        # since page_size = 4096 and qsz <= 128, queue_alloc <= 0x2000
        self.queue_alloc = self.used_offs + align(used_size)

        self.memory = dev_util.Memory()
        self.memory.write(0, [0]*self.queue_alloc)

        self.avail_ring_info = dev_util.Layout(self.memory, self.avail_offs, {
            'flags': (0, 2),
            'idx': (2, 2)
        }, True)

        self.used_ring_info = dev_util.Layout(self.memory, self.used_offs, {
            'flags': (0, 2),
            'idx': (2, 2)
        }, True)

        self.used_idx = 0
        self.avail_idx = 0
        self.empty = True

    @property
    def desc_head(self):
        return self.used_idx % self.qsz

    @property
    def desc_tail(self):
        return self.avail_idx % self.qsz

    def add_desc(self, desc, write_only=False):
        if (self.desc_head == self.desc_tail) and not self.empty:
            raise Exception('Avail ring out of space')

        self.empty = False

        desc_id = self.desc_tail

        (desc_addr, desc_len) = desc

        write_addr = desc_id*16
        addr_field = desc_addr.to_bytes(8, 'little')
        len_field = desc_len.to_bytes(4, 'little')
        flags_field = (2 if write_only else 0).to_bytes(2, 'little')
        next_field = (0).to_bytes(2, 'little')
        self.memory.write(write_addr,
                          addr_field + len_field + flags_field + next_field)

        self.memory.write(self.avail_offs + 2*2 + desc_id*2,
                          desc_id.to_bytes(2, 'little'))
        self.avail_idx = (self.avail_idx + 1) & 0xffff
        self.avail_ring_info.idx = self.avail_idx

    def get_used_descs(self):
        new_used_idx = self.used_ring_info.idx
        used_bufs = []
        while (self.used_idx != new_used_idx):
            desc_id = self.desc_head
            used_desc = self.memory.read(self.used_offs + 2*2 + desc_id*8, 8)
            used_id = int.from_bytes(used_desc[0:4], 'little')
            used_len = int.from_bytes(used_desc[4:8], 'little')
            if (used_id != desc_id):
                raise Exception('Out of order used buffer returns')

            desc = self.memory.read(used_id*16, 12)
            desc_addr = int.from_bytes(desc[0:8], 'little')
            desc_len = int.from_bytes(desc[8:12], 'little')

            used_bufs.append(((desc_addr, desc_len), used_len))
            self.used_idx = (self.used_idx + 1) & 0xffff

        if used_bufs and (self.desc_head == self.desc_tail):
            self.empty = True

        return used_bufs

class signal_target(dev_util.iface('signal')):
    def __init__(self):
        self.raised = False
    def signal_raise(self, obj):
        self.raised = True
    def signal_lower(self, obj):
        self.raised = False

class ethernet_link(dev_util.iface('ethernet_common')):
    def __init__(self):
        self.frames = []
    def frame(self, sim_obj, frame, crc_status):
        self.frames.append((frame, crc_status))

    def clear(self):
        self.frames.clear()

def create_virtio_mmio_blk(name=None):
    '''Create a new virtio_mmio_blk object'''
    irq_target = dev_util.Dev([signal_target])
    image = simics.pre_conf_object(name, 'image')
    image.size = 0x1000
    memory_space = simics.pre_conf_object(name, 'memory-space')
    virtio = simics.pre_conf_object(name, 'virtio_mmio_blk')
    virtio.irq = irq_target.obj
    virtio.image = image
    virtio.phys_mem = memory_space
    simics.SIM_add_configuration([virtio, image, memory_space], None)
    return {'obj': simics.SIM_get_object(virtio.name),
            'image': image,
            'irq_target': irq_target
            }


def create_virtio_pcie_blk(name=None):
    '''Create a new virtio_pcie_blk object'''
    image = simics.SIM_create_object('image',  None, size=0x1000)
    virtio = simics.SIM_create_object('virtio_pcie_blk', name, image=image)
    return {'obj': virtio, 'image': image}

def create_virtio_pcie_sriov_blk(name=None):
    '''Create a new virtio-pcie-sriov-blk object'''
    images = [simics.SIM_create_object('image',  None, size=0x1000) for i in range(6)]
    virtio = simics.SIM_create_object('virtio-pcie-sriov-blk', name, image=images)
    return {'obj': virtio, 'images': images}

def create_virtio_mmio_net(name=None):
    '''Create a new virtio_mmio_net object'''
    irq_target = dev_util.Dev([signal_target])
    eth_link = dev_util.Dev([ethernet_link])
    memory_space = simics.pre_conf_object(name, 'memory-space')
    virtio = simics.pre_conf_object(name, 'virtio_mmio_net')
    virtio.irq = irq_target.obj
    virtio.port.eth.link = eth_link.obj
    virtio.phys_mem = memory_space
    simics.SIM_add_configuration([virtio, memory_space], None)
    return {'obj': simics.SIM_get_object(virtio.name),
            'irq_target': irq_target,
            'eth_link': eth_link
            }

def create_virtio_mmio_entropy(name=None, seed=0xdeadbeef):
    '''Create a new virtio_mmio_entropy object'''
    irq_target = dev_util.Dev([signal_target])
    memory_space = simics.pre_conf_object(name, 'memory-space')
    virtio = simics.pre_conf_object(name, 'virtio-mmio-entropy')
    virtio.irq = irq_target.obj
    virtio.phys_mem = memory_space
    virtio.seed = seed
    simics.SIM_add_configuration([virtio, memory_space], None)
    return {'obj': simics.SIM_get_object(virtio.name),
            'irq_target': irq_target,
            }

def create_virtio_pcie_fs(name=None, tag_name='simics'):
    '''Create a new virtio_pcie_fs object'''
    virtio = simics.SIM_create_object('virtio_pcie_fs', name,
                                      tag_name=tag_name)
    return {'obj': virtio}

def send_frame(virtio, frame, crc_status):
    return virtio.port.eth.iface.ethernet_common.frame(frame, crc_status)


def write_ram(img: simics.conf_object_t, addr: int, data: bytes):
    img.iface.image.set(addr, data)


def read_ram(img: simics.conf_object_t, addr: int, size: int) -> bytes:
    return img.iface.image.get(addr, size)


VIRTIO_STATUS_ACKNOWLEDGE = 0x01
VIRTIO_STATUS_DRIVER      = 0x02
VIRTIO_STATUS_DRIVER_OK   = 0x04
VIRTIO_STATUS_FEATURES_OK = 0x08
VIRTIO_STATUS_NEEDS_RESET = 0x40
VIRTIO_STATUS_FAILED      = 0x80

class FeaturesRejected(Exception):
    def __init__(self):
        Exception.__init__(self, 'supported feature set rejected by device')



def initialize_virtio(virtio, supported_features = [0, 0],
                      num_queues = 1):
    status              = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x70)
    hst_features_sel    = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x14)
    hst_features        = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x10)
    gst_features_sel    = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x24)
    gst_features        = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x20)
    virtio['obj'].port.SRESET.iface.signal.signal_raise()
    virtio['obj'].port.SRESET.iface.signal.signal_lower()
    status.write(VIRTIO_STATUS_ACKNOWLEDGE)
    status.write(VIRTIO_STATUS_DRIVER)
    for i in range(2):
        hst_features_sel.write(i)
        gst_features_sel.write(i)
        gst_features.write(hst_features.read() & supported_features[i])
    # Legacy interfaces skip steps 5 and 6 of initialization
    queue_mems = setup_queues(virtio, num_queues)
    status.write(VIRTIO_STATUS_DRIVER_OK)
    return queue_mems

def setup_queues(virtio, num_queues):
    # GuestPageSize
    dev_util.Register_LE(virtio['obj'].bank.mmio, 0x28).write(page_size)

    virtq_mems = []
    for i in range(num_queues):
        # QueueSel
        dev_util.Register_LE(virtio['obj'].bank.mmio, 0x30).write(i)

        queue_num = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x38)
        queue_num_max = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x34)
        qsz = min(128, queue_num_max.read())
        queue_num.write(qsz)

        dev_util.Register_LE(virtio['obj'].bank.mmio, 0x28).write(4096)

        virtq_mem = VirtQueueMem(qsz)

        virtio['obj'].phys_mem.map += [
            [0x1000000 + 0x2000 * i, virtq_mem.memory.obj, 0, 0,
             virtq_mem.queue_alloc]
        ]

        # QueueAlign
        dev_util.Register_LE(virtio['obj'].bank.mmio, 0x3c).write(page_size)

        # QueuePFN
        (dev_util.Register_LE(virtio['obj'].bank.mmio, 0x40)
         .write(0x1000000//page_size + 2*i))

        virtq_mems.append(virtq_mem)
    return virtq_mems


class VirtioQueuePCIE:

    def __init__(self, queue_size: int, queue_desc_addr: int,
                 queue_driver_addr: int, queue_device_addr: int,
                 img_iface: simics.image_interface_t):
        self.queue_size = queue_size
        self._queue_desc_addr = queue_desc_addr
        self._queue_driver_addr = queue_driver_addr
        self._queue_device_addr = queue_device_addr
        self._img_iface = img_iface

        self._next_desc_idx = 0
        self._desc_chains: Dict[int, None] = {}

    def enable_interrupt_response(self):
        avail_flags_fmt = '<H'
        avail_flags = 0
        self._img_iface.set(self._queue_driver_addr,
                            struct.pack(avail_flags_fmt, avail_flags))

    def disable_interrupt_response(self):
        avail_flags_fmt = '<H'
        avail_flags = 1
        self._img_iface.set(self._queue_driver_addr,
                            struct.pack(avail_flags_fmt, avail_flags))

    def _commit_free_desc_idx(self) -> int:
        while self._next_desc_idx in self._desc_chains:
            if self._next_desc_idx == self.queue_size - 1:
                self._next_desc_idx = 0
            else:
                self._next_desc_idx += 1
        self._desc_chains[self._next_desc_idx] = None
        return self._next_desc_idx

    def _find_free_desc_idx(self) -> int:
        next_desc_idx = self._next_desc_idx
        while next_desc_idx in self._desc_chains:
            if next_desc_idx == self.queue_size - 1:
                next_desc_idx = 0
            else:
                next_desc_idx += 1
        return next_desc_idx

    def give_buffers(self, buffers: List[Dict]) -> int:
        avail_header_fmt = '<HH'
        avail_header = self._img_iface.get(
            self._queue_driver_addr, avail_header_len)
        _, avail_idx = struct.unpack(avail_header_fmt, avail_header)
        avail_pos = avail_idx % self.queue_size

        for i, buffer in enumerate(buffers):
            desc_idx = self._commit_free_desc_idx() % self.queue_size

            if i == 0:
                head_desc_idx = desc_idx
                self._img_iface.set(
                    self._queue_driver_addr + avail_header_len +
                    (struct.calcsize("<H") * avail_pos),
                    struct.pack("<H", head_desc_idx))

            desc_fmt = '<QLHH'
            if i != len(buffers) - 1:
                chain_next = self._find_free_desc_idx() % self.queue_size
                self._desc_chains[desc_idx] = chain_next
            else:
                chain_next = 0
            desc = struct.pack(desc_fmt, buffer['addr'], buffer['len'],
                               buffer['flags'], chain_next)

            self._img_iface.set(self._queue_desc_addr +
                                desc_idx * struct.calcsize(desc_fmt), desc)

        if avail_idx == 65535:
            avail_idx = 0
        else:
            avail_idx += 1
        self._img_iface.set(self._queue_driver_addr,
                            struct.pack(avail_header_fmt, 0, avail_idx))
        return head_desc_idx

    def last_used_buffers(self) -> Tuple[int, int]:
        used_idx = (self.get_used_ring_next() - 1) % self.queue_size
        id, len = self.get_used_ring(used_idx)
        if id in self._desc_chains:
            next = id
            while True:
                curr = next
                next = self._desc_chains[curr]
                self._desc_chains.pop(curr)
                if next is None:
                    break
            return (id, len)
        else:
            raise RuntimeError("The used id provided by the device did not " +
                               "exist in the available buffer")

    def get_used_ring_next(self) -> int:
        used_header_fmt = '<HH'
        used_header = self._img_iface.get(
            self._queue_device_addr, used_header_len)
        _, used_idx = struct.unpack(used_header_fmt, used_header)
        return used_idx

    def get_used_ring(self, idx: int) -> Dict[str, int]:
        used_elem_fmt = '<II'
        offset = self._queue_device_addr + used_header_len + \
            idx * struct.calcsize(used_elem_fmt)
        used_elem = self._img_iface.get(offset, struct.calcsize(used_elem_fmt))
        return struct.unpack(used_elem_fmt, used_elem)


class VirtioDevicePCIE:
    def __init__(
        self: TVirtioDevicePCIE,
        dev_obj: simics.conf_object_t,
        ram_img: simics.conf_object_t,
        queues_starting_offset: int = 0
    ):
        self.dev_obj = dev_obj
        self.ram_img = ram_img
        self.queues_starting_offset = queues_starting_offset
        self.bar0_memory_address = 0
        self.queues: List[VirtioQueuePCIE] = []

        self.queues_mem_end = 0

        self.pcie_config_regs: types.SimpleNamespace
        self.virtio_config_regs: types.SimpleNamespace
        self.msix_table_regs: types.SimpleNamespace

        self.retrieve_registers()

    def retrieve_registers(self: TVirtioDevicePCIE):
        self.pcie_config_regs = dev_util.bank_regs(self.dev_obj.bank.pcie_config)
        self.virtio_config_regs = dev_util.bank_regs(self.dev_obj.bank.virtio_config)
        self.msix_table_regs = dev_util.bank_regs(self.dev_obj.bank.msix_data)


    def _device_virtq_discovery(self: TVirtioDevicePCIE,
                                expected_num_queues: int):
        self.num_queues = (
            self.virtio_config_regs.common_config.num_queues.read())
        if self.num_queues != expected_num_queues:
            raise RuntimeError("Unexpected amount of virtqueues in device")

        self.queue = []
        offset = self.queues_starting_offset
        for i in range(self.num_queues):
            self.virtio_config_regs.common_config.queue_select.write(i)
            self.virtio_config_regs.common_config.queue_msix_vector.write(
                i + 1)
            queue_size = (
                self.virtio_config_regs.common_config.queue_size.read())

            queue_desc = offset + 2
            queue_driver = queue_desc + 16 * queue_size
            queue_device = queue_driver + 6 * 2 * queue_size
            queue = VirtioQueuePCIE(queue_size, queue_desc, queue_driver,
                                    queue_device, self.ram_img.iface.image)
            self.queues.append(queue)

            self.virtio_config_regs.common_config.queue_desc.write(queue_desc)
            self.virtio_config_regs.common_config.queue_driver.write(
                queue_driver)
            self.virtio_config_regs.common_config.queue_device.write(
                queue_device)

            offset += ((16 * queue_size) + (6 * 2 * queue_size) +
                       (6 * 8 * queue_size)) + 2
        self.queues_mem_end = offset

    def _check_feature_bits(self, expected_device_features: int,
                            features_enabled: int):
        device_features_reg = (
            self.virtio_config_regs.common_config.device_feature)
        device_features_select_reg = (
            self.virtio_config_regs.common_config.device_feature_select)
        driver_features_reg = (
            self.virtio_config_regs.common_config.driver_feature)
        driver_features_select_reg = (
            self.virtio_config_regs.common_config.driver_feature_select)

        expected_device_features = expected_device_features.to_bytes(
            N_FEATURE_REGS * 4,
            'little')

        features_enabled_bytes = features_enabled.to_bytes(
            N_FEATURE_REGS * 4, 'little')

        for i in range(0, N_FEATURE_REGS):
            device_features_select_reg.write(i)
            driver_features_select_reg.write(i)

            feature_bits = device_features_reg.read()

            if feature_bits != int.from_bytes(
                    expected_device_features[4*i:(4*i)+4], 'little'):
                return False

            common = feature_bits & int.from_bytes(
                features_enabled_bytes[4*i:(4*i)+4], 'little')
            driver_features_reg.write(common)

        return True

    def init_device(
        self: TVirtioDevicePCIE,
        expected_num_queues: int = 1,
        device_specific_setup: Optional[Callable[[TVirtioDevicePCIE], None]] = None,
        expected_device_features: int = (1 << VIRTIO_F_VERSION_1)
        | (1 << VIRTIO_F_ACCESS_PLATFORM),
    ) -> int:
        self.pcie_config_regs.command.write(dev_util.READ, m=1)
        device_status = self.virtio_config_regs.common_config.device_status

        if device_status.read() != 0:
            raise RuntimeError("Device has not been reset before init")

        device_status.write(VIRTIO_STATUS_ACKNOWLEDGE | device_status.read())
        device_status.write(VIRTIO_STATUS_DRIVER | device_status.read())

        if (not self._check_feature_bits(expected_device_features,
                                         expected_device_features)):
            print("Feature bit check failed")
            return device_status.read()
        device_status.write(VIRTIO_STATUS_FEATURES_OK | device_status.read())

        self.pcie_config_regs.msix.control.write(dev_util.READ, enable=1)
        self.pcie_config_regs.msix.control.write(dev_util.READ, mask=1)
        self._device_virtq_discovery(expected_num_queues)
        if device_specific_setup is not None:
            device_specific_setup(self)
        device_status.write(VIRTIO_STATUS_DRIVER_OK | device_status.read())

        self.enable_virtio_config_regs()

        return device_status.read()

    def enable_virtio_config_regs(self: TVirtioDevicePCIE):
        # This is just to be able to access virtio_pcie bank using the bar
        self.pcie_config_regs.bar0.write(-1)
        bar_read = self.pcie_config_regs.bar0.read()
        if (bar_read & 0xF) != 0xC:
            raise RuntimeError(
                "BAR0 is expected to have a memory space indicator, be 64 bits and be preferable"
            )
        if (bar_read & 0xFFFFFFFFFFFFFFF0) != 0xFFFFFFFFFFFFC000:
            raise RuntimeError("BAR0 is expected to have 14 size bits")
        self.pcie_config_regs.bar0.write(0x50000)
        self.pcie_config_regs.command.write(dev_util.READ, mem=1)

    def notify(self: TVirtioDevicePCIE, queue: int):
        self.virtio_config_regs.notify.virtqueue_available_buffer.write(queue)

    def validate_msix_status(self: TVirtioDevicePCIE, vector: int) -> bool:
        pending = self.msix_table_regs.pending[int(vector / 32)].read()
        if ((1 << (vector % 32)) & pending) != 0:
            self.msix_table_regs.pending[int(vector / 32)].write(0)
            return True
        return False


class VirtioPCIEVirtualFunction(VirtioDevicePCIE):
    def __init__(
        self: TVirtioPCIEVirtualFunction,
        dev_obj: simics.conf_object_t,
        ram_img: simics.conf_object_t,
        queues_starting_offset: int,
    ):
        super().__init__(
            dev_obj,
            ram_img,
            queues_starting_offset=queues_starting_offset,
        )

    def enable_virtio_config_regs(self: TVirtioPCIEVirtualFunction):
        pass
