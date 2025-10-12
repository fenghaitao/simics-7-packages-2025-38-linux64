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

//:: pre doc {{

#include <simics/base/log.h>
#include <simics/base/memory.h>
#include <simics/base/transaction.h>

#include <iostream>

#include "pcie-shim.h"


class PcieShimStub : public ShimPcie {
  public:
    explicit PcieShimStub(simics::ConfObjectRef obj) : ShimPcie(obj) {}

    static void init_class(simics::ConfClass *cls) {
        ShimPcie::init_class(cls);
    }

  private:
    void
    forward_message(write_completion_t completion,
                    uint64_t addr,
                    pcie_message_type_t mtype,
                    pcie_msg_route_t route,
                    uint16_t bdf,
                    std::vector<uint8_t> &payload) override;

    void
    forward_mem_read(read_completion_t completion, uint64_t addr,
                     size_t size) override;

    void
    forward_mem_write(write_completion_t completion,
                      uint64_t addr, std::vector<uint8_t> &buf) override;

    void
    forward_cfg_write(write_completion_t completion,
                      bool type0, uint16_t bdf, uint16_t ofs,
                      std::vector<uint8_t> &buf) override;

    void
    forward_cfg_read(read_completion_t completion,
                     bool type0, uint16_t bdf, uint16_t ofs,
                     size_t size) override;

    void
    forward_io_write(write_completion_t completion,
                     uint64_t addr, std::vector<uint8_t> &buf) override;

    void
    forward_io_read(read_completion_t completion,
                    uint64_t addr, size_t size) override;

    void hot_reset() override;
};


void
PcieShimStub::forward_message(write_completion_t completion,
                              uint64_t addr,
                              pcie_message_type_t mtype,
                              pcie_msg_route_t route,
                              uint16_t bdf,
                              std::vector<uint8_t> &payload) { 
    SIM_LOG_INFO(3, obj(), 0,
        "Discarding message %s %s",
        ShimPcie::msg_type_str(mtype),
        ShimPcie::msg_route_str(route));
    completion(Sim_PE_No_Exception);
}

void
PcieShimStub::forward_mem_read(read_completion_t completion, uint64_t addr,
                               size_t size) {
    std::vector<uint8_t> bytes(size);
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
        "Discarding read write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + size - 1));
    completion(Sim_PE_No_Exception, bytes);
}

void
PcieShimStub::forward_mem_write(write_completion_t completion, uint64_t addr,
                                std::vector<uint8_t> &buf) {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
        "Discarding memory write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));
    completion(Sim_PE_No_Exception);
}

void
PcieShimStub::forward_cfg_write(write_completion_t completion,
                                bool type0, uint16_t bdf, uint16_t ofs,
                                std::vector<uint8_t> &buf) {
    uint64_t addr = ofs;
    if (!type0)
        addr += (static_cast<uint64_t>(bdf)) << 16;

    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
        "Discarding config Type%d write @ 0x%zx-0x%zx",
        type0 ? 0 : 1,
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));

    completion(Sim_PE_No_Exception);
}

void
PcieShimStub::forward_cfg_read(read_completion_t completion,
                               bool type0, uint16_t bdf,
                               uint16_t ofs, size_t size) {
    uint64_t addr = ofs;
    if (!type0)
        addr += (static_cast<uint64_t>(bdf)) << 16;

    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
        "Discarding config Type%d read @ 0x%zx-0x%zx",
        type0 ? 0 : 1,
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + size - 1));

    std::vector<uint8_t> bytes(size);
    completion(Sim_PE_No_Exception, bytes);
}

void
PcieShimStub::forward_io_write(write_completion_t completion,
                               uint64_t addr, std::vector<uint8_t> &buf) {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
    "Discarding IO write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));
    completion(Sim_PE_No_Exception);
}

void
PcieShimStub::forward_io_read(read_completion_t completion,
                              uint64_t addr, size_t size) {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0,
        "Discarding IO read @ 0x%zx-0x%zx",
        static_cast<size_t>(addr), static_cast<size_t>(addr + size - 1));

    std::vector<uint8_t> bytes(size);
    completion(Sim_PE_No_Exception, bytes);
}

void
PcieShimStub::hot_reset() {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0, "Hot-reset unimplemented");
}

extern "C" void init_stub() try {
    simics::make_class<PcieShimStub>(
    "pcie-shim-stub",
    "a PCIe Shim to external API (stub)",
    "Shim that forwards Simics PCIe transaction to an external entity");
} catch(const std::exception& e) {
    std::cerr << e.what() << std::endl;
}
// }}
