// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/cc-api.h>
#include <string>

#include "sample-dma-device.h"
#include "register-as-data.h"

namespace {
bool is_big_endian() {
    union {
        uint32_t i;
        char c[4];
    } test = {0x01020304};

    // If the first byte is 1, it's big-endian
    return test.c[0] == 1;
}

size_t swap_endianness(size_t value, size_t byte_count = 4) {
    size_t result = 0;

    for (size_t i = 0; i < byte_count; ++i) {
        result |= ((value >> (i * 8)) & 0xFF) << ((byte_count - 1 - i) * 8);
    }

    return result;
}
}  // namespace

void SampleDmaDevice::init_class(simics::ConfClass *cls) {
    simics::create_hierarchy_from_register_data<SampleDmaDevice>(cls, data);

    cls->add(simics::Attribute("target_mem", "o",
                               "The memory space on which the DMA engine "
                               "operates. Data will be read from and copied "
                               "to the memory associated with this memory "
                               "space.",
                               ATTR_CLS_VAR(SampleDmaDevice, target_mem_space_),
                               Sim_Attr_Required));
    cls->add(simics::Attribute("intr_target", "o",
                               "Interrupt target port to signal on DMA "
                               "interrupts.",
                               ATTR_CLS_VAR(SampleDmaDevice, intr_target_),
                               Sim_Attr_Required));
    cls->add(simics::Attribute("throttle", "f",
                               "Delay in seconds per 32-bit word of memory "
                               "copied, default is 1μs.",
                               ATTR_CLS_VAR(SampleDmaDevice, throttle_)));

    cls->add(simics::EventInfo("timer_irq",
                               EVENT_CALLBACK(SampleDmaDevice, timer_irq_ev)));
}

SampleDmaDevice::ControlRegister::ControlRegister(
        simics::MappableConfObject *dev_obj,
        const std::string &name)
    : Register(dev_obj, name),
      convert_endianness_(!is_big_endian()) {}

void SampleDmaDevice::ControlRegister::TcField::
write(uint64_t val, uint64_t enabled_bits) {
    // Set to 1 when transfer completed by device itself.
    // Clear by writing a zero.
    // If interrupts are enabled and interrupt status is one
    // also clear the interrupt in the processor.
    if (val != 0) {
        SIM_LOG_SPEC_VIOLATION(1, bank_obj_ref(), 0,
                               "write one to TC - ignored");
        return;
    }

    if (get() == 0) {  // Already cleared
        return;
    }

    SIM_LOG_INFO(3, bank_obj_ref(), 0,
                 "write zero to TC - clearing TC");
    set(0);

    if (!interrupt_posted_) {
        return;
    }

    SIM_LOG_INFO(3, bank_obj_ref(), 0,
                 "also clearing interrupt on CPU");
    interrupt_posted_ = false;  // remember cleared
    dev_ptr<SampleDmaDevice>()->intr_target_.iface().signal_lower();
}

void SampleDmaDevice::ControlRegister::
read_mem(void *dst, size_t src, size_t len) {
    exception_type_t exc = dev_ptr<SampleDmaDevice>()
        ->target_mem_space_.iface().access_simple(
                bank_obj_ref(), src, static_cast<uint8 *>(dst), len,
                Sim_RW_Read, Sim_Endian_Target);

    if (exc != Sim_PE_No_Exception) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "an error occurred when reading target memory");
        throw std::runtime_error {
            "an error occurred when reading target memory"
        };
    }
}

void SampleDmaDevice::ControlRegister::
write_mem(size_t dst, uint8_t *src, size_t len) {
    exception_type_t exc = dev_ptr<SampleDmaDevice>()
        ->target_mem_space_.iface().access_simple(bank_obj_ref(),
                                                  dst,
                                                  src,
                                                  len,
                                                  Sim_RW_Write,
                                                  Sim_Endian_Target);

    if (exc != Sim_PE_No_Exception) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "an error occurred when writing to target "
                      "memory");
        throw std::runtime_error {
            "an error occurred when writing to target memory"
        };
    }
}

void SampleDmaDevice::ControlRegister::
copy_contiguous(size_t dst, size_t src, unsigned count) {
    uint8_t buf[count];  // NOLINT(runtime/arrays)
    read_mem(buf, src, count);
    write_mem(dst, buf, count);
}

bool SampleDmaDevice::ControlRegister::
next_row(size_t *addr, size_t *end_addr) {
    bool finished;
    sg_list_block_row_t block_row;
    read_mem(&block_row, *addr, sizeof block_row);
    if (convert_endianness_) {
        block_row.addr = swap_endianness(block_row.addr);
        block_row.len = swap_endianness(block_row.len, 2);
    }
    bool ext = block_row.flags & 1;
    if (ext) {
        *addr = block_row.addr + block_row.offset;
        *end_addr = *addr + block_row.len;
    } else {
        *addr = *addr + sizeof block_row;
    }
    finished = *addr == *end_addr;
    return finished;
}

unsigned SampleDmaDevice::ControlRegister::
copy_scatter_gather(size_t dst, size_t src) {
    unsigned copied_bytes;
    // Get the header data
    sg_list_head_t head;
    read_mem(&head, src, sizeof head);
    if (convert_endianness_) {
        head.addr = swap_endianness(head.addr);
        head.len = swap_endianness(head.len, 2);
    }
    copied_bytes = 0;

    size_t addr = head.addr;
    size_t end_addr = head.addr + head.len;
    size_t hare_addr = addr;
    size_t hare_end_addr = end_addr;

    // Continue running through the lists until the end is reached
    // or an error has been detected
    sg_list_block_row_t row;
    bool finished = false;
    bool hare_finished = false;
    while (!finished && lookup_field("ERR")->get() == 0) {
        read_mem(&row, addr, sizeof row);
        if (convert_endianness_) {
            row.addr = swap_endianness(row.addr);
            row.len = swap_endianness(row.len, 2);
        }
        bool ext = row.flags & 1;
        if (!ext) {  // Data block
            SIM_LOG_INFO_STR(
                    4, bank_obj_ref(), 0,
                    fmt::format("Data block of length {} at {:#010x}"
                                " with offset {}", row.len, row.addr,
                                row.offset));
            // Copy a block of data
            copy_contiguous(dst, row.addr + row.offset, row.len);
            dst += row.len;
            copied_bytes += row.len;
        } else {
            SIM_LOG_INFO_STR(
                    4, bank_obj_ref(), 0,
                    fmt::format("Extension block of length {} at"
                                " {:#010x} with offset {}", row.len,
                                row.addr, row.offset));
        }

        finished = next_row(&addr, &end_addr);

        // Check for loops.
        if (!hare_finished) {
            int i;
            // Hare moves through lists at double the speed of addr.
            // If the hare ends up at the same address as addr, a loop
            // has been detected, if the hare reaches the end there is
            // no loop.
            for (i = 0; i < 2; i++) {
                hare_finished = next_row(&hare_addr, &hare_end_addr);
                if (hare_finished) {
                    SIM_LOG_INFO(4, bank_obj_ref(), 0,
                                 "Loop checker finished, no loops");
                    break;
                }
            }
            if (hare_addr == addr) {
                SIM_LOG_SPEC_VIOLATION(1, bank_obj_ref(), 0,
                                       "Stuck in a loop.");
                lookup_field("ERR")->set(1);
            }
        }
    }
    return copied_bytes;
}

void SampleDmaDevice::ControlRegister::complete_dma() {
    // Log that completion is done
    SIM_LOG_INFO(2, bank_obj_ref(), 0, "DMA transfer completed");

    // clear SWT bit, update TS
    lookup_field("SWT")->set(0);
    lookup_field("TS")->set(0);
    tc.set(1);

    // raise interrupt towards CPU
    if (lookup_field("ECI")->get() == 0) {
        SIM_LOG_INFO(3, bank_obj_ref(), 0,
                     "ECI is zero, no interrupt raised");
        return;
    }

    SIM_LOG_INFO(3, bank_obj_ref(), 0, "raising interrupt signal");
    dev_ptr<SampleDmaDevice>()->intr_target_.iface().signal_raise();

    // remember that we raised it
    tc.interrupt_posted_ = true;
}

void SampleDmaDevice::ControlRegister::do_dma_transfer() {
    if (lookup_field("SWT")->get() == 0) {
        // No need to do anything if we are not asked by software
        return;
    }

    // Software asked us to initiate a DMA transfer
    if (lookup_field("EN")->get() == 0) {
        // enable bit not set, so we cannot transfer
        SIM_LOG_INFO(2, bank_obj_ref(), 0,
                     "EN bit not set, SWT = 1 has no effect");
        return;
    }

    SIM_LOG_INFO(3, bank_obj_ref(), 0,
                 "EN bit set, SWT written, initiating DMA");
    auto dest = lookup_register("dest")->get();
    auto source = lookup_register("source")->get();
    SIM_LOG_INFO_STR(3, bank_obj_ref(), 0,
                     fmt::format("Transferring {} 32-bit words from"
                                 " {:#010x} to {:#010x}",
                                 lookup_field("TS")->get(), source,
                                 dest));

    unsigned count = lookup_field("TS")->get() * 4;
    try {
        if (lookup_field("SG")->get() != 0) {
            SIM_LOG_INFO(4, bank_obj_ref(), 0,
                         "Scatter Gather Transfer");
            count = copy_scatter_gather(dest, source);
        } else {
            SIM_LOG_INFO(4, bank_obj_ref(), 0, "Contiguous Transfer");
            copy_contiguous(dest, source, count);
        }
    } catch (const std::exception &e) {
        SIM_LOG_ERROR(bank_obj_ref(), 0, "DMA memory access failed");
        return;
    }

    dev_ptr<SampleDmaDevice>()->timer_irq_ev.post(
            dev_ptr<SampleDmaDevice>()->throttle_ * count / 4.0,
            nullptr);
}

void SampleDmaDevice::ControlRegister::
write(uint64_t value, uint64_t enabled_bits) {
    Register::write(value, enabled_bits);
    do_dma_transfer();
}

void SampleDmaDevice::SimpleTimeEvent::callback(lang_void *) {
    dev_->control.complete_dma();
}

extern "C" void init_local() {
    simics::make_class<SampleDmaDevice>(
            "sample_dma_device_cpp",
            "example DMA device",
            "Example of a DMA device supporting contiguous memory or "
            " scatter-gather lists. The device has a controllable throughput "
            " (words per second) and supports either polling mode or interrupt "
            " based signalling upon DMA completion.");
}
