// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SAMPLE_DMA_DEVICE_H
#define SAMPLE_DMA_DEVICE_H

#include <simics/c++/devs/memory-space.h>
#include <simics/c++/devs/signal.h>
#include <simics/cc-api.h>
#include <simics/cc-modeling-api.h>

#include <cstddef>
#include <cstdint>
#include <string>

class SampleDmaDevice : public simics::MappableConfObject {
  public:
    explicit SampleDmaDevice(simics::ConfObjectRef o)
        : simics::MappableConfObject(o) {}

    static void init_class(simics::ConfClass *cls);

    class ControlRegister : public simics::Register {
      public:
        ControlRegister(simics::MappableConfObject *dev_obj,
                        const std::string &name);

        void complete_dma();

      private:
        struct sg_list_head_t {
            uint32_t addr;
            uint16_t len;
            uint16_t reserved;
        };

        struct sg_list_block_row_t {
            uint32_t addr;
            uint16_t len;
            uint8_t offset;
            uint8_t flags;
        };

        class TcField : public simics::Field {
          public:
            using Field::Field;

            void write(uint64_t val, uint64_t enabled_bits) override;
            bool interrupt_posted_ {false};
        };

        void read_mem(void *dst, size_t src, size_t len);
        // Write len bytes to target memory from the memory pointed to by
        // src. The data is written to the memory space $target_mem_space at
        // address dst. If a memory access error occurs this method will
        // print an error message and throw an exception.
        void write_mem(size_t dst, uint8_t *src, size_t len);

        void copy_contiguous(size_t dst, size_t src, unsigned count);

        // next_row - Returns the address to next row to be processed.
        // end_addr is the address after the end of the block, if this address
        // is reached the transaction should have finished
        bool next_row(size_t *addr, size_t *end_addr);

        unsigned copy_scatter_gather(size_t dst, size_t src);
        void do_dma_transfer();
        void write(uint64_t value, uint64_t enabled_bits) override;

        TcField tc {dev_obj(), "regs.control.TC"};
        bool convert_endianness_ {false};
    };

    class SimpleTimeEvent : public simics::TimeEvent<SampleDmaDevice> {
      public:
        explicit SimpleTimeEvent(simics::ConfObject *obj)
            : TimeEvent(obj, event_cls) {}

        inline static event_class_t *event_cls = nullptr;

        void callback(lang_void *data = nullptr) override;
    };

  private:
    double throttle_ {1e-6};
    simics::Connect<simics::iface::MemorySpaceInterface> target_mem_space_;
    simics::Connect<simics::iface::SignalInterface> intr_target_;
    simics::BigEndianBank regs {this, "regs"};
    ControlRegister control {this, "regs.control"};
    SimpleTimeEvent timer_irq_ev {this};
};

#endif  // SAMPLE_DMA_DEVICE_H
