/*                                                              -*- C++ -*-

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SYSTEMC_DMA_DEVICE_DMA_DEVICE_H
#define SYSTEMC_DMA_DEVICE_DMA_DEVICE_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>

#include <cstdint>  // uint32_t

class DMADevice : public sc_core::sc_module {
  public:
    SC_CTOR(DMADevice);

    tlm_utils::simple_target_socket<DMADevice> mmio_socket_;
    tlm_utils::simple_initiator_socket<DMADevice> phys_mem_socket_;
    sc_core::sc_out<bool> interrupt_;
    sc_core::sc_in<bool> reset_;

    // Delay in seconds per 32-bit word of memory copied
    double throttle_ {1.0e-6};

  private:
    using Register = uint32_t;
    using Payload = tlm::tlm_generic_payload;

    struct {
        Register dma_control;      // Control register
        Register dma_source;       // Source address
        Register dma_destination;  // Destination address
    } regs_;

    enum MMIO_Offset {
        MMIO_CONTROL = 0,
        MMIO_SOURCE = 4,
        MMIO_DEST = 8,
    };

    enum ControlBits {
        EN  = 31,
        SWT = 30,
        ECI = 29,
        TC  = 28,
        SG  = 27,
        ERR = 26,
        RF  = 25,  // run-forever, used by Simics benchmarks
        TS_MSB  = 15,
        TS_LSB  = 0
    };

    void b_transport(Payload &trans, sc_core::sc_time &t);  // NOLINT
    unsigned int transport_dbg(Payload &trans);  // NOLINT
    bool get_direct_mem_ptr(Payload &trans, tlm::tlm_dmi &dmi); // NOLINT
    void invalidate_direct_mem_ptr(sc_dt::uint64 start_range,
                                   sc_dt::uint64 end_range);

    void onReadWriteRegisterAccess(Register *reg, Payload *trans);
    void onControlRegisterAccess(Payload *trans);
    void doDMATransfer(sc_dt::sc_uint<32> old_val);
    void completeDMA();
    void triggerTransaction();
    void processTransaction(Payload *trans);
    void readMem(void *buf, uint32_t addr, uint32_t count);
    void writeMem(uint32_t addr, const void *buf, uint32_t count);
    void onReset();
    void toggleInterrupt();
    void outboundTransaction(Payload *pl, tlm::tlm_dmi *dmi_data);

    tlm::tlm_dmi dmi_src_data_;
    tlm::tlm_dmi dmi_dst_data_;

    sc_core::sc_event dma_complete_;
    sc_core::sc_event interrupt_toggle_;
    sc_core::sc_event trigger_transaction_;
};

#endif
