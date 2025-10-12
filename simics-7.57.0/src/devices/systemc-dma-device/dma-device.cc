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

#include "dma-device.h"

#include <iomanip>  // showbase
#include <sstream>
#include <cstring>  // memcpy
#include <utility>  // swap
#include <vector>

using sc_core::SC_MEDIUM;
using sc_core::SC_HIGH;

#define TAG "intel/sample-dma-device"

namespace {
bool inRange(sc_dt::uint64 value, sc_dt::uint64 start, sc_dt::uint64 end) {
    return start <= value && value <= end;
}

void invalidateDirectMemPtr(sc_dt::uint64 start_range,
                            sc_dt::uint64 end_range,
                            tlm::tlm_dmi *dmi_data) {
    if (inRange(dmi_data->get_start_address(), start_range, end_range)
        || inRange(dmi_data->get_end_address(), start_range, end_range)) {
        dmi_data->allow_none();
    }
}

bool dmiAllowed(const tlm::tlm_dmi &dmi_data_,
                tlm::tlm_dmi::dmi_access_e access_type,
                uint32_t addr, uint32_t count) {
    if (dmi_data_.get_granted_access() & access_type) {
        if (dmi_data_.get_start_address() <= addr
            && dmi_data_.get_end_address() + 1 >= addr + count) {
            return true;
        }
    }

    return false;
}

void waitMaybe(sc_core::sc_time delay) {
    if (delay != sc_core::SC_ZERO_TIME) {
        sc_core::wait(delay);
    }
}

void preparePayload(tlm::tlm_generic_payload *pl, uint32_t addr,
                    uint32_t count, void *buf) {
    pl->set_address(addr);
    pl->set_data_length(count);
    pl->set_data_ptr(static_cast<unsigned char*>(buf));
    pl->set_streaming_width(count);
}

}  // namespace

DMADevice::DMADevice(sc_core::sc_module_name name)
    : sc_module(name),
      mmio_socket_("mmio"),
      phys_mem_socket_("phys_mem"),
      interrupt_("interrupt"),
      reset_("reset") {
    memset(&regs_, 0, sizeof regs_);

    SC_METHOD(completeDMA);
    sensitive << dma_complete_;
    dont_initialize();
    SC_METHOD(toggleInterrupt);
    sensitive << interrupt_toggle_;
    dont_initialize();
    SC_METHOD(triggerTransaction);
    sensitive << trigger_transaction_;
    dont_initialize();

    mmio_socket_.register_b_transport(this, &DMADevice::b_transport);
    mmio_socket_.register_transport_dbg(this, &DMADevice::transport_dbg);
    mmio_socket_.register_get_direct_mem_ptr(this,
                                             &DMADevice::get_direct_mem_ptr);

    phys_mem_socket_.register_invalidate_direct_mem_ptr(
        this, &DMADevice::invalidate_direct_mem_ptr);

    SC_METHOD(onReset);
    sensitive << reset_.pos();

    SC_REPORT_INFO_VERB(TAG, "Waiting for completion event", SC_HIGH);
}

void DMADevice::onReadWriteRegisterAccess(Register *reg, Payload *trans) {
    void *src = trans->get_data_ptr();
    void *dst = reg;

    if (trans->is_read()) {
        std::swap(src, dst);
    }

    std::memcpy(dst, src, sizeof *reg);
}

void DMADevice::onControlRegisterAccess(Payload *trans) {
    sc_dt::sc_uint<32> ctrl = regs_.dma_control;
    onReadWriteRegisterAccess(&regs_.dma_control, trans);
    if (trans->is_write()) {
        doDMATransfer(ctrl);
    }
}

void DMADevice::doDMATransfer(sc_dt::sc_uint<32> old_val) {
    sc_dt::sc_uint<32> ctrl = regs_.dma_control;
    std::ostringstream log;
    log << "doDMATransfer 0x" << std::hex << ctrl;
    SC_REPORT_INFO_VERB(TAG, log.str().c_str(), SC_HIGH);

    // Software asked us to initiate a DMA transfer
    if (!ctrl[EN]) {
        // Enable bit is not set, so we cannot transfer
        SC_REPORT_INFO(TAG, "EN bit not set, SWT = 1 has no effect");
        return;
    }

    if (ctrl[TC]) {
        SC_REPORT_INFO(TAG "/spec-viol", "Write 1 to TC is not allowed");
        ctrl[TC] = old_val[TC];
    } else {
        if (old_val[TC] && interrupt_) {
            SC_REPORT_INFO_VERB(TAG, "Clear interrupt", SC_MEDIUM);
            interrupt_toggle_.notify();
        }
    }

    if (!ctrl[SWT])
        return;  // No need to do anything if we are not asked by software

    uint32_t count = 4 * ctrl.range(TS_MSB, TS_LSB);
    std::vector<unsigned char> buf(count);
    readMem(&buf[0], regs_.dma_source, count);
    writeMem(regs_.dma_destination, &buf[0], count);

    double delay = count / 4 * throttle_;
    sc_core::sc_time t(delay * 1.0e9, sc_core::SC_NS);
    log.str("");
    log << "Notify completion in " << t;
    SC_REPORT_INFO_VERB(TAG, log.str().c_str(), SC_MEDIUM);
    dma_complete_.notify(t);
}

void DMADevice::outboundTransaction(Payload *pl, tlm::tlm_dmi *dmi_data) {
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
    Payload dmi_pl;
    dmi_pl.deep_copy_from(*pl);

    phys_mem_socket_->b_transport(*pl, delay);
    if (!pl->is_response_ok()) {
        SC_REPORT_WARNING(TAG, "Transaction failed");
    } else if (pl->is_dmi_allowed()) {
        SC_REPORT_INFO_VERB(TAG, "DMI allowed, request DMI access", SC_HIGH);
        dmi_data->init();
        bool granted = phys_mem_socket_->get_direct_mem_ptr(dmi_pl, *dmi_data);
        SC_REPORT_INFO_VERB(TAG, granted ? "DMI granted" : "DMI not granted",
                            SC_HIGH);
    }

    waitMaybe(delay);
}

void DMADevice::readMem(void *buf, uint32_t addr, uint32_t count) {
    std::ostringstream log;
    log << "ReadMem from 0x" << std::showbase << std::hex << addr
        << ", size 0x" << count;
    SC_REPORT_INFO_VERB(TAG, log.str().c_str(), SC_HIGH);

    if (dmiAllowed(dmi_src_data_, tlm::tlm_dmi::DMI_ACCESS_READ, addr, count)) {
        SC_REPORT_INFO_VERB(TAG, "DMI read access", SC_MEDIUM);
        std::memcpy(buf,
               dmi_src_data_.get_dmi_ptr() + addr
               - dmi_src_data_.get_start_address(), count);

        waitMaybe(dmi_src_data_.get_read_latency());
    } else {
        Payload pl;
        preparePayload(&pl, addr, count, buf);
        pl.set_read();
        outboundTransaction(&pl, &dmi_src_data_);
    }
}

void DMADevice::writeMem(uint32_t addr, const void *buf, uint32_t count) {
    std::ostringstream log;
    log << "WriteMem to 0x" << std::showbase << std::hex << addr
        << ", size 0x" << count;
    SC_REPORT_INFO_VERB(TAG, log.str().c_str(), SC_HIGH);

    if (dmiAllowed(dmi_dst_data_, tlm::tlm_dmi::DMI_ACCESS_WRITE,
                   addr, count)) {
        SC_REPORT_INFO_VERB(TAG, "DMI write access", SC_MEDIUM);
        std::memcpy(dmi_dst_data_.get_dmi_ptr() + addr
               - dmi_dst_data_.get_start_address(), buf, count);

        waitMaybe(dmi_dst_data_.get_write_latency());
    } else {
        Payload pl;
        preparePayload(&pl, addr, count, const_cast<void*>(buf));
        pl.set_write();
        outboundTransaction(&pl, &dmi_dst_data_);
    }
}

void DMADevice::onReset() {
    SC_REPORT_INFO_VERB(TAG, "Reset triggered", SC_MEDIUM);
    memset(&regs_, 0, sizeof regs_);
}

void DMADevice::completeDMA() {
    SC_REPORT_INFO_VERB(TAG, "DMA transfer completed", SC_HIGH);

    sc_dt::sc_uint<32> ctrl = regs_.dma_control;
    if (ctrl[RF]) {
        // Run-forever? Don't clear SWT bit, instead schedule a new DMA
        // transfer in 0.01 seconds
        trigger_transaction_.notify(10, sc_core::SC_MS);
    } else {
        // Clear SWT bit, update TS
        ctrl[SWT] = 0;
        ctrl.range(TS_MSB, TS_LSB) = 0;
        ctrl[TC] = 1;
        regs_.dma_control = ctrl;
    }

    if (ctrl[ECI] && !interrupt_) {
        SC_REPORT_INFO_VERB(TAG, "Raise interrupt", SC_MEDIUM);
        interrupt_toggle_.notify();
    }

    SC_REPORT_INFO_VERB(TAG, "Waiting for completion event", SC_HIGH);
}

void DMADevice::b_transport(Payload &trans, sc_core::sc_time &t) {
    // Synchronize
    wait(t);
    t = sc_core::SC_ZERO_TIME;
    processTransaction(&trans);
}

void DMADevice::triggerTransaction() {
    SC_REPORT_INFO_VERB(TAG, "triggerTransaction()", SC_MEDIUM);
    doDMATransfer(0);  // old ctrl value not used in RF mode
}

void DMADevice::processTransaction(Payload *trans) {
    sc_dt::uint64 offset = trans->get_address();
    unsigned int size = trans->get_data_length();

    if (size != sizeof(Register)) {
        // IEEE Std 1666-2011 (14.17,g) suggests to use response
        // TLM_GENERIC_ERROR_RESPONSE to stand for a non-specific error
        trans->set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
        return;
    }

    // assume OK, handlers will signal error
    trans->set_response_status(tlm::TLM_OK_RESPONSE);

    switch (offset) {
    case MMIO_CONTROL:
        if (trans->is_read())
            SC_REPORT_INFO_VERB(TAG, "Read control register", SC_HIGH);
        else
            SC_REPORT_INFO_VERB(TAG, "Write control register", SC_HIGH);
        onControlRegisterAccess(trans);
        break;
    case MMIO_SOURCE:
        if (trans->is_read())
            SC_REPORT_INFO_VERB(TAG, "Read source register", SC_HIGH);
        else
            SC_REPORT_INFO_VERB(TAG, "Write source register", SC_HIGH);
        trans->set_dmi_allowed(true);
        onReadWriteRegisterAccess(&regs_.dma_source, trans);
        break;
    case MMIO_DEST:
        if (trans->is_read())
            SC_REPORT_INFO_VERB(TAG, "Read destination register", SC_HIGH);
        else
            SC_REPORT_INFO_VERB(TAG, "Write destination register", SC_HIGH);
        trans->set_dmi_allowed(true);
        onReadWriteRegisterAccess(&regs_.dma_destination, trans);
        break;
    default:
        trans->set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
        break;
    }
}

void DMADevice::toggleInterrupt() {
    interrupt_ = !interrupt_;
}

unsigned int DMADevice::transport_dbg(Payload &trans) {
    unsigned int size = trans.get_data_length();
    sc_dt::uint64 start = trans.get_address();
    sc_dt::uint64 end = start + size;

    if (end > sizeof regs_) {
        trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
        return 0;
    }

    unsigned char *src = trans.get_data_ptr();
    unsigned char *dst = reinterpret_cast<unsigned char*>(&regs_) + start;

    if (trans.is_read())
        std::swap(src, dst);

    std::memcpy(dst, src, size);

    trans.set_response_status(tlm::TLM_OK_RESPONSE);
    return trans.get_data_length();
}

void DMADevice::invalidate_direct_mem_ptr(sc_dt::uint64 start_range,
                                          sc_dt::uint64 end_range) {
    SC_REPORT_INFO_VERB(TAG, "Invalidate direct mem ptr", SC_HIGH);
    invalidateDirectMemPtr(start_range, end_range, &dmi_dst_data_);
    invalidateDirectMemPtr(start_range, end_range, &dmi_src_data_);
}

bool DMADevice::get_direct_mem_ptr(Payload &trans,
                                   tlm::tlm_dmi &dmi) {
    SC_REPORT_INFO_VERB(TAG, "Request DMI access", SC_HIGH);
    switch (trans.get_address()) {
    case MMIO_DEST:
    case MMIO_SOURCE:
        dmi.set_dmi_ptr(reinterpret_cast<unsigned char*>(&regs_.dma_source));
        dmi.set_start_address(MMIO_SOURCE);
        dmi.set_end_address(MMIO_DEST + sizeof(Register));
        dmi.allow_read_write();
        break;

    default:
        return false;
    }

    return true;
}
