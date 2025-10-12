/*                                  -*- C++ -*-

  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SAMPLE_PCIE_SHIM_PCIE_SHIM_H
#define SAMPLE_PCIE_SHIM_PCIE_SHIM_H

#include <simics/base/transaction.h>
#include <simics/cc-api.h>
#include <simics/c++/devs/pci.h>
#include <simics/c++/devs/translator.h>
#include <simics/c++/model-iface/transaction.h>

#include <cstdint>
#include <string>
#include <map>
#include <vector>
#include <functional>

//:: pre doc {{

class ShimPcie : public simics::ConfObject,
                 public simics::iface::TransactionInterface,
                 public simics::iface::PciePortControlInterface,
                 public simics::EnableAfterCall<ShimPcie> {
  public:
    explicit ShimPcie(simics::ConfObjectRef obj)
        : simics::ConfObject(obj),
          simics::EnableAfterCall<ShimPcie>(this),
          up_map_target(NULL) {}

    /* Transaction interface called whenever receiving an upstream transaction */
    exception_type_t issue(transaction_t *t, uint64 addr) override;

    /* PCIe port control interface */
    void set_secondary_bus_number(uint64 value) override;
    void hot_reset() override;

    /* Upstream transactions user has to call */
    exception_type_t
    upstream_message(pcie_message_type_t mtype,
                     pcie_msg_route_t route,
                     uint16_t bdf,
                     std::vector<uint8_t> &payload);

    exception_type_t
    upstream_mem_read(uint64_t addr, std::vector<uint8_t> &buf);

    exception_type_t
    upstream_mem_write(uint64_t addr, std::vector<uint8_t> &buf);

    simics::MapTargetConnect upstream_target {this->obj()};

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::iface::TransactionInterface::Info());
        cls->add(simics::iface::PciePortControlInterface::Info());
        cls->add(simics::Attribute("upstream_target", "o|n",
        "Target to forward upstream PCIe transactions",
            ATTR_CLS_VAR(ShimPcie, upstream_target)));
        cls->add(ShimPcie::afterEventInfo());
    }

    /* Completion functions to be called after done with processing
     * the read/write PCIe transaction.
     */ 
    typedef std::function<void(exception_type_t)> write_completion_t;
    typedef std::function<void(exception_type_t, std::vector<uint8_t>&)> read_completion_t;

  private:
    map_target_t *up_map_target;

    void handle_transaction(uintptr_t _t, uint64 addr);

    /* Forwards PCIe downstream transactions into external system.
     * Implemented by user. User has to called the completion function
     * when done with processing the transaction.
     */
    virtual void
    forward_message(write_completion_t completion,
                    uint64_t addr,
                    pcie_message_type_t mtype, pcie_msg_route_t route,
                    uint16_t bdf, std::vector<uint8_t> &payload) = 0;

    virtual void
    forward_mem_read(read_completion_t completion, uint64_t addr, size_t size) = 0;

    virtual void
    forward_mem_write(write_completion_t completion,
                      uint64_t addr, std::vector<uint8_t> &buf) = 0;

    virtual void
    forward_cfg_write(write_completion_t completion,
                      bool type0, uint16_t bdf, uint16_t ofs,
                      std::vector<uint8_t> &buf) = 0;

    virtual void
    forward_cfg_read(read_completion_t completion, bool type0, uint16_t bdf,
                     uint16_t ofs, size_t size) = 0;

    virtual void
    forward_io_write(write_completion_t completion, uint64_t addr,
                     std::vector<uint8_t> &buf) = 0;

    virtual void
    forward_io_read(read_completion_t completion, uint64_t addr, size_t size) = 0;

// }}
  public:
    static const char* pcie_type_name(pcie_type_t t) {
        std::map<pcie_type_t, std::string> map = {
            { PCIE_Type_Not_Set, "Not Set"},
            { PCIE_Type_Mem,     "Memory"},
            { PCIE_Type_IO,      "I/O"},
            { PCIE_Type_Cfg,     "Config"},
            { PCIE_Type_Msg,     "Message"},
            { PCIE_Type_Other,   "Other"},
        };
        try {
            return map.at(t).c_str();
        } catch (const std::out_of_range&) {
            return "Unknown";
        }
    }
    static const char* msg_type_str(pcie_message_type_t mt) {
        /* Return the name as described in the PCIe Specification */
        std::map<pcie_message_type_t, std::string> map = {
        { PCIE_ATS_Invalidate, "ATS Invalidate Request" },
        { PCIE_ATS_Invalidate_Completion, "ATS Invalidate Completion" },
        { PCIE_PRS_Request, "PRS Request" },
        { PCIE_PRS_Response, "PRG Response" },
        { PCIE_Latency_Tolerance_Reporting,
            "Latency Tolerance Reporting" },
        { PCIE_Optimized_Buffer_Flush_Fill,
            "Optimized Buffer Flush Fill" },
        { PCIE_Msg_Assert_INTA, "Assert_INTA" },
        { PCIE_Msg_Assert_INTB, "Assert_INTB" },
        { PCIE_Msg_Assert_INTC, "Assert_INTC" },
        { PCIE_Msg_Assert_INTD, "Assert_INTD" },
        { PCIE_Msg_Deassert_INTA, "Deassert_INTA" },
        { PCIE_Msg_Deassert_INTB, "Deassert_INTB" },
        { PCIE_Msg_Deassert_INTC, "Deassert_INTC" },
        { PCIE_Msg_Deassert_INTD, "Deassert_INTD"},
        { PCIE_PM_Active_State_Nak, "PM_Active_State_Nak"},
        { PCIE_PM_PME, "PM_PME"},
        { PCIE_PM_Turn_Off, "PME_Turn_Off"},
        { PCIE_PM_PME_TO_Ack, "PME_TO_Ack"},
        { PCIE_ERR_COR, "ERR_COR"},
        { PCIE_ERR_NONFATAL, "ERR_NONFATAL"},
        { PCIE_ERR_FATAL, "ERR_FATAL"},
        { PCIE_Unlock, "Unlock"},
        { PCIE_Set_Slot_Power_Limit, "Set_Slot_Power_Limit"},
        { PCIE_Precision_Time_Measurement,
            "Precision Time Measurement"},
        { PCIE_HP_Power_Indicator_On, "Power Indicator On" },
        { PCIE_HP_Power_Indicator_Blink, "Power Indicator Blink"},
        { PCIE_HP_Power_Indicator_Off, "Power Indicator Off" },
        { PCIE_HP_Attention_Button_Pressed,
            "Attention Button Pressed" },
        { PCIE_HP_Attention_Indicator_On, "Attention Indicator On" },
        { PCIE_HP_Attention_Indicator_Blink,
            "Attention Indicator Blink" },
        { PCIE_HP_Attention_Indicator_Off, "Attention Indicator Off" },
        { PCIE_Vendor_Defined_Type_0, "Vendor_Defined Type 0" },
        { PCIE_Vendor_Defined_Type_1, "Vendor_Defined Type 1" },
        };
        try {
            return map.at(mt).c_str();
        } catch (const std::out_of_range&) {
            return "Unknown";
        }
    }
    static const char* msg_route_str(pcie_msg_route_t mr) {
        std::map<pcie_msg_route_t, std::string> map = {
            { PCIE_Msg_Route_Not_Set, "Routing Rule Not set" },
            { PCIE_Msg_Route_Upstream, "Routed to Root Complex" },
            { PCIE_Msg_Route_Address, "Routed by Address" },
            { PCIE_Msg_Route_ID, "Routed by ID" },
            { PCIE_Msg_Route_Broadcast, "Broadcast from Root Complex" },
            { PCIE_Msg_Route_Terminate,
            "Local - Terminate at Receiver" },
            { PCIE_Msg_Route_Gather,
            "Gathered and routed to Root Complex" },
        };
        try {
            return map.at(mr).c_str();
        } catch (const std::out_of_range&) {
            return "Routing Unknown";
        }
    }
};

#endif  // SAMPLE_PCIE_SHIM_PCIE_SHIM_H
