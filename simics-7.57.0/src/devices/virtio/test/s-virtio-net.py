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

virtio = virtio_common.create_virtio_mmio_net()

[receive_q_virtq,
 transmit_q_virtq] = virtio_common.initialize_virtio(virtio, num_queues = 2)

receive_q_id = 0
transmit_q_id = 1

receive_q_mem = dev_util.Memory()
receive_q_mem_offset = 0x100000

transmit_q_mem = dev_util.Memory()
transmit_q_mem_offset = 0x200000

simics.SIM_run_command('%s.log-level 2' % virtio['obj'].name)
simics.SIM_run_command('%s.log-group -enable virtio_net'
                       % virtio['obj'].name)

virtio['obj'].phys_mem.map += [
    [receive_q_mem_offset, receive_q_mem.obj, 0, 0, 1526*128],
    [transmit_q_mem_offset, transmit_q_mem.obj, 0, 0, 1526*128]
]

def prepare_receive_bufs(count = 1, offset = 0):
    for i in range(count):
        addr = receive_q_mem_offset + offset + 1526*i
        receive_q_mem.write(addr, b'\0'*1526)
        desc = (addr, 1526)
        receive_q_virtq.add_desc(desc, True)

def prepare_transmit(payload = b'', offset = 0):
    # all zero virtio net header (sizeof(virtio_net_hdr_t) == 10)
    transmit_q_mem.write(offset, b'\0'*10 + payload)
    desc = (transmit_q_mem_offset + offset, 10 + len(payload))
    transmit_q_virtq.add_desc(desc)

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

def to_eth_payload(payload):
    if len(payload) < 60: # ETHER_MIN_LEN - ETHER_CRC_LEN
        return payload.ljust(64, b'\0')
    else:
        return payload + b'\0'*4

def test_packet_transmit(payloads):
    eth_link = virtio['eth_link'].ethernet_common
    eth_link.clear()

    for (i, payload) in enumerate(payloads):
        prepare_transmit(payload, i*1526)
    notify(transmit_q_id)
    expect_used_buffer_notification()

    stest.expect_equal(eth_link.frames,
                       [(to_eth_payload(payload), simics.Eth_Frame_CRC_Match)
                        for payload in payloads]
                       )
    stest.expect_equal(transmit_q_virtq.get_used_descs(),
                       [((transmit_q_mem_offset + i*1526, len(payload) + 10),
                         0)
                        for (i, payload) in enumerate(payloads)]
                       )
    ack_interrupt()

def expect_receive_used(payloads):
    used_descs = receive_q_virtq.get_used_descs()

    stest.expect_equal(len(used_descs), len(payloads))
    for (i, (frame, ((desc_addr, desc_len), desc_used))) in \
        enumerate(zip(payloads, used_descs)):
        stest.expect_equal(desc_addr, receive_q_mem_offset + i*1526)
        stest.expect_equal(desc_len, 1526)

        # sizeof(virtio_net_hdr_t) == 10
        # Device strips away CRC field (ETHER_CRC_LEN == 4)
        stest.expect_equal(desc_used, len(frame) + 10 - 4)
        written_payload = receive_q_mem.read(i*1526 + 10, len(frame) - 4)
        stest.expect_equal(bytes(written_payload) + b'\0'*4, frame)


def test_packet_receive(payloads):
    if not payloads:
        return

    payloads = list(map(to_eth_payload, payloads))
    prepare_receive_bufs(len(payloads))
    notify(receive_q_id)
    stest.expect_false(virtio['irq_target'].signal.raised)

    # Tell device not to interrupt driver
    receive_q_virtq.avail_ring_info.flags |= 1
    for payload in payloads[:-1]:
        virtio_common.send_frame(virtio['obj'], payload,
                                 simics.Eth_Frame_CRC_Match)
        stest.expect_false(virtio['irq_target'].signal.raised)

    # Allow device to interrupt driver
    receive_q_virtq.avail_ring_info.flags &= ~1
    virtio_common.send_frame(virtio['obj'], payloads[-1],
                             simics.Eth_Frame_CRC_Match)

    expect_used_buffer_notification()
    expect_receive_used(payloads)

    ack_interrupt()

# Test device behavior when device is given insufficient available receive
# buffers from the driver
def test_receive_starvation(propagated, dropped):
    if propagated:
        prepare_receive_bufs(len(propagated))
        notify(receive_q_id)

    propagated = list(map(to_eth_payload, propagated))
    dropped = list(map(to_eth_payload, dropped))

    for payload in propagated:
        virtio_common.send_frame(virtio['obj'], payload,
                                 simics.Eth_Frame_CRC_Match)
        expect_used_buffer_notification()
        ack_interrupt()

    simics.SIM_run_command('%s.log-level 3' % virtio['obj'].name)
    for payload in dropped:
        # Receive buffer starvation causes a relatively high-severity info log
        # (1 then 3)
        stest.expect_log(virtio_common.send_frame,
                         [virtio['obj'], payload, simics.Eth_Frame_CRC_Match],
                         virtio['obj'], 'info')
    simics.SIM_run_command('%s.log-level 2' % virtio['obj'].name)

    expect_receive_used(propagated)

    if virtio['irq_target'].signal.raised:
        ack_interrupt()


payload_empty = b''

payload_small = bytes(i for i in range(56))

# ETHER_MIN_LEN - ETHER_CRC_LEN
payload_min = bytes(i for i in range(60))

payload_mid = bytes(i & 0xff for i in range(782))

# ETHER_MAX_LEN - ETHER_CRC_LEN
payload_max = bytes(i & 0xff for i in range(1514))

payloads = [payload_empty, payload_small, payload_min, payload_mid,
            payload_max]

for payload in payloads:
    test_packet_transmit([payload])
    test_packet_receive([payload])

test_packet_transmit(payloads)
test_packet_receive(payloads)


# test filling out the receive_q/transmit_q queues
test_packet_transmit([str(i).encode() for i in range(128)])

test_packet_receive([str(i).encode() for i in range(128)])

propagated = [f'propagated {i}'.encode() for i in range(32)]
dropped = [f'dropped {i}'.encode() for i in range(32)]

test_receive_starvation([], dropped)
test_receive_starvation(propagated, dropped)
