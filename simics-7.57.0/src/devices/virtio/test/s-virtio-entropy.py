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
import stest
import dev_util
import virtio_common
import random
import statistics
import tempfile

random.seed("entropy")

virtio = virtio_common.create_virtio_mmio_entropy()

[request_q_virtq] = virtio_common.initialize_virtio(virtio, num_queues = 1)
request_q_id = 0

request_q_mem = dev_util.Memory()
request_q_mem_offset = 0x100000

virtio['obj'].phys_mem.map += [
    [request_q_mem_offset, request_q_mem.obj, 0, 0, 1000],
]

def notify(virtq_idx):
    notify_reg = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x50)
    notify_reg.write(virtq_idx)

def expect_used_buffer_notification():
    stest.expect_true(virtio['irq_target'].signal.raised)
    interrupt_status = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x60)
    stest.expect_equal(interrupt_status.read(), 1)

def ack_interrupt():
    interrupt_ack = dev_util.Register_LE(virtio['obj'].bank.mmio, 0x64)
    interrupt_ack.write(1)
    stest.expect_false(virtio['irq_target'].signal.raised)

def prepare_request_buf(size):
    addr = request_q_mem_offset
    request_q_mem.write(addr, b'\0'*size)
    desc = (addr, size)
    request_q_virtq.add_desc(desc, True)

def test_requesting_entropy():
    size = random.randrange(50, 100)

    prepare_request_buf(size)
    notify(request_q_id)
    stest.expect_true(virtio['irq_target'].signal.raised)

    expect_used_buffer_notification()
    ack_interrupt()

    [((desc_addr, desc_len), used_len)] = request_q_virtq.get_used_descs()
    stest.expect_equal(used_len, size)
    stest.expect_equal(desc_len, size)
    stest.expect_equal(request_q_mem_offset, desc_addr)

    entropy = request_q_mem.read(0, size)
    bad_entropy = [(i % 256) for i in range(size)]

    stest.expect_true(statistics.variance(entropy) >
                      (2 * statistics.variance(bad_entropy)))
    stest.expect_true(statistics.stdev(entropy) >
                      (2 * statistics.stdev(bad_entropy)))

def test_unique_seed():
    global request_q_mem
    virtio1 = virtio_common.create_virtio_mmio_entropy(seed=0xabcd)
    virtio2 = virtio_common.create_virtio_mmio_entropy(seed=0x1234)

    virtio1['obj'].phys_mem.map += [
        [request_q_mem_offset, request_q_mem.obj, 0, 0, 1000],
    ]
    virtio2['obj'].phys_mem.map += [
        [request_q_mem_offset, request_q_mem.obj, 0, 0, 1000],
    ]

    size = 4

    [request_q1] = virtio_common.initialize_virtio(virtio1, num_queues = 1)
    [request_q2] = virtio_common.initialize_virtio(virtio2, num_queues = 1)

    addr1 = request_q_mem_offset
    addr2 = addr1 + size
    request_q_mem.write(addr1, b'\0'*size)
    request_q_mem.write(addr2, b'\0'*size)

    desc1 = (addr1, size)
    desc2 = (addr2, size)
    request_q1.add_desc(desc1, True)
    request_q2.add_desc(desc2, True)

    notify_reg = dev_util.Register_LE(virtio1['obj'].bank.mmio, 0x50)
    notify_reg.write(0)
    entropy1 = request_q_mem.read(0, size)
    notify_reg = dev_util.Register_LE(virtio2['obj'].bank.mmio, 0x50)
    notify_reg.write(0)
    entropy2 = request_q_mem.read(size, size)

    stest.expect_different(entropy1, entropy2)
    stest.expect_equal(entropy1, [0x80, 0xd5, 0x33, 0xb])
    stest.expect_equal(entropy2, [0x76, 0x47, 0x79, 0x47])


def test_checkpointing():
    global request_q_mem
    global virtio
    global request_q_virtq

    size = 50

    with tempfile.TemporaryDirectory() as tmpdir:
        cpfile = os.path.join(tmpdir, "virtio-entropy.cp")
        name = virtio['obj'].name
        simics.SIM_write_configuration_to_file(cpfile, 0)

        prepare_request_buf(size)
        notify(request_q_id)
        expect_used_buffer_notification()
        ack_interrupt()

        entropy0 = request_q_mem.read(0, size)

        simics.SIM_delete_objects(list(simics.SIM_object_iterator(None)))

        simics.SIM_read_configuration(cpfile)
        virtio = { 'obj': simics.SIM_get_object(name) }

        virtio['obj'].phys_mem.map = []
        old_queue = request_q_virtq
        [request_q_virtq] = virtio_common.setup_queues(virtio, num_queues = 1)
        request_q_virtq.used_idx = old_queue.used_idx
        request_q_virtq.avail_idx = old_queue.avail_idx

        request_q_mem = dev_util.Memory()
        request_q_mem.write(0, b'\0'*size)

        virtio['obj'].phys_mem.map += [
            [request_q_mem_offset, request_q_mem.obj, 0, 0, 1000],
        ]

        prepare_request_buf(size)
        notify(request_q_id)

        entropy1 = request_q_mem.read(0, size)
        stest.expect_equal(entropy0, entropy1)


for i in range(10):
    test_requesting_entropy()

test_checkpointing()
test_unique_seed()
