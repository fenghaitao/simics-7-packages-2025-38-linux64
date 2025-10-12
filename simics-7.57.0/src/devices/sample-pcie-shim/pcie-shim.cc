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

#include "pcie-shim.h"
#include <iostream>
#include <simics/base/memory.h>

exception_type_t
ShimPcie::issue(transaction_t *t, uint64 addr) {
    SIM_LOG_INFO(4, obj(), 0,
        "Received upstream transaction @ 0x%llx-0x%llx",
        addr, addr + SIM_transaction_size(t) - 1);

    pcie_type_t type = ATOM_get_transaction_pcie_type(t);
    unsigned size = SIM_transaction_size(t);
    uint16_t bdf = ATOM_get_transaction_pcie_device_id(t);

    SIM_LOG_INFO(4, obj(), 0,
        "Received upstream %s transaction @ 0x%llx-0x%llx",
        pcie_type_name(type), addr, addr + size - 1);

    if (type == PCIE_Type_Not_Set) {
        SIM_LOG_ERROR(obj(), 0, "Error: No PCIe type atom");
        return Sim_PE_IO_Error;
    }
    if (type >= PCIE_Type_Other) {
        SIM_LOG_ERROR(obj(), 0,
            "Error: Invalid PCIe type atom %d", type);
        return Sim_PE_IO_Error;
    }

    std::vector<uint8_t> bytes(size);

    exception_type_t ret = Sim_PE_Last;  /* I.e. not set */
    if (SIM_transaction_is_read(t)) {
        read_completion_t
        completion = [t, this, addr, &ret](exception_type_t ex, std::vector<uint8_t>& buf) {
            if (ex == Sim_PE_No_Exception) {
                SIM_set_transaction_bytes(
                    t, {buf.data(), buf.size()});
            }
            SIM_LOG_INFO(3, this->obj(), 0, "%s %s read transaction @ 0x%llx-0x%llx",
                ex == Sim_PE_No_Exception ? "Completed" : "Error: ",
                ex == Sim_PE_No_Exception ? "" : SIM_describe_pseudo_exception(ex),
                addr, addr + SIM_transaction_size(t) - 1);
            ret = ex;
        };
        if (type == PCIE_Type_Mem) {
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding memory read transaction @ 0x%llx-0x%llx",
                addr, addr + SIM_transaction_size(t) - 1);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_mem_read(completion, addr, size);
        } else if (type == PCIE_Type_Cfg) {
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding config read transaction bdf=%x:%x:%x @ 0x%llx-0x%llx",
                bdf>>8, (bdf & 0xff)>>3, bdf & 0x7,
                (addr & 0xffff), (addr & 0xffff) + SIM_transaction_size(t) - 1);
            bool type0 = (bdf >> 8) != 0 && ((addr >> 24) == 0);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_cfg_read(completion, type0, bdf,
                                   addr & 0xffff, size);
        } else {  // IO
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding io read transaction @ 0x%llx-0x%llx",
                addr, addr + SIM_transaction_size(t) - 1);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_io_read(completion, addr, size);
        }
        if (ret == Sim_PE_Last) {
            SIM_LOG_ERROR(obj(), 0, "Error: No completion for read transaction");
            return Sim_PE_IO_Error;
        } else {
            return ret;
        }
    } else {  // Write transaction
        write_completion_t completion = [t, this, addr, &ret](exception_type_t ex) {
            SIM_LOG_INFO(3, this->obj(), 0, "%s %s write transaction @ 0x%llx-0x%llx",
                ex == Sim_PE_No_Exception ? "Completed" : "Error: ",
                ex == Sim_PE_No_Exception ? "" : SIM_describe_pseudo_exception(ex),
                addr, addr + SIM_transaction_size(t) - 1);
            ret = ex;
        };
        if (SIM_transaction_is_inquiry(t)) {
            SIM_LOG_INFO(1, obj(), 0,
            "Aborting transaction, does not support inquiry write");
            return Sim_PE_Inquiry_Unhandled;
        }

        SIM_get_transaction_bytes(t, {bytes.data(), size});
        if (type == PCIE_Type_Msg) {
            pcie_message_type_t mtype =
                ATOM_get_transaction_pcie_msg_type(t);
            pcie_msg_route_t route =
                ATOM_get_transaction_pcie_msg_route(t);
            if (route == PCIE_Msg_Route_ID) {
                SIM_LOG_INFO(3, obj(), 0,
                    "Forwarding message %s %s bdf=%x:%x:%x",
                    ShimPcie::msg_type_str(mtype),
                    ShimPcie::msg_route_str(route),
                    bdf>>8, (bdf & 0xff)>>3, bdf & 0x7);
            } else {
                SIM_LOG_INFO(3, obj(), 0,
                    "Forwarding message %s %s",
                    ShimPcie::msg_type_str(mtype),
                    ShimPcie::msg_route_str(route));
            }

            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_message(completion, addr, mtype,
                                  route, bdf, bytes);
        } else if (type == PCIE_Type_Mem) {
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding mem write transaction @ 0x%llx-0x%llx",
                addr, addr + SIM_transaction_size(t) - 1);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_mem_write(completion, addr, bytes);
        } else if (type == PCIE_Type_Cfg) {
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding config write transaction bdf=%x:%x:%x @ 0x%llx-0x%llx",
                bdf>>8, (bdf & 0xff)>>3, bdf & 0x7,
                (addr & 0xffff), (addr & 0xffff) + SIM_transaction_size(t) - 1);
            bool type0 = (bdf >> 8) != 0 && ((addr >> 24) == 0);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_cfg_write(completion, type0, bdf,
                                    addr & 0xffff, bytes);
        } else {  // IO
            SIM_LOG_INFO(3, obj(), 0,
            "Forwarding io write transaction @ 0x%llx-0x%llx",
                addr, addr + SIM_transaction_size(t) - 1);
            // coverity[copy_instead_of_move:SUPPRESS]
            this->forward_io_write(completion, addr, bytes);
        }
        if (ret == Sim_PE_Last) {
            SIM_LOG_ERROR(obj(), 0, "Error: No completion for read transaction");
            return Sim_PE_IO_Error;
        } else {
            return ret;
        }
    }
}

void ShimPcie::set_secondary_bus_number(uint64 value) {
    SIM_LOG_INFO(4, obj(), 0, "PCIe set secondary bus number");
}

void
ShimPcie::hot_reset() {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0, "PCIe hot reset requested");
}

exception_type_t
ShimPcie::upstream_message(pcie_message_type_t mtype,
                           pcie_msg_route_t route,
                           uint16_t bdf,
                           std::vector<uint8_t> &payload) {
    atom_t atoms[] = {
        ATOM_flags(Sim_Transaction_Write),
        ATOM_data(payload.data()),
        ATOM_size(payload.size()),
        ATOM_pcie_type(PCIE_Type_Msg),
        ATOM_pcie_msg_type(mtype),
        ATOM_pcie_msg_route(route),
        route == PCIE_Msg_Route_ID ?
            ATOM_pcie_device_id(bdf) : ATOM_LIST_END,
        ATOM_LIST_END
    };
    if (route == PCIE_Msg_Route_ID) {
        SIM_LOG_INFO(3, obj(), 0,
            "Upstream message %s %s bdf=%x:%x:%x",
            ShimPcie::msg_type_str(mtype),
            ShimPcie::msg_route_str(route),
            bdf>>8, (bdf & 0xff)>>3, bdf & 0x7);
    } else {
        SIM_LOG_INFO(3, obj(), 0,
            "Upstream message %s %s",
            ShimPcie::msg_type_str(mtype),
            ShimPcie::msg_route_str(route));
    }
    transaction_t t = { .atoms = atoms };
    return SIM_issue_transaction(this->upstream_target.map_target(), &t,
        route == PCIE_Msg_Route_ID ?
            (static_cast<uint64_t>(bdf)) << 48 : 0);
}

exception_type_t
ShimPcie::upstream_mem_read(uint64_t addr, std::vector<uint8_t> &buf) {
    SIM_LOG_INFO(4, obj(), 0,
        "Upstream MEM Read @ 0x%zx-0x%zx",
        static_cast<size_t>(addr), static_cast<size_t>(addr + buf.size() - 1));
    atom_t atoms[] = {
        ATOM_flags(Sim_Transaction_Fetch),
        ATOM_data(buf.data()),
        ATOM_size(buf.size()),
        ATOM_pcie_type(PCIE_Type_Mem),
        ATOM_LIST_END
    };
    transaction_t t = { .atoms = atoms };
    return SIM_issue_transaction(this->upstream_target.map_target(), &t, addr);
}

exception_type_t
ShimPcie::upstream_mem_write(uint64_t addr, std::vector<uint8_t> &buf) {
    SIM_LOG_INFO(4, obj(), 0,
        "Upstream MEM Write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr), static_cast<size_t>(addr + buf.size() - 1));
    atom_t atoms[] = {
        ATOM_flags(Sim_Transaction_Write),
        ATOM_data(buf.data()),
        ATOM_size(buf.size()),
        ATOM_pcie_type(PCIE_Type_Mem),
        ATOM_LIST_END
    };
    transaction_t t = { .atoms = atoms };
    return SIM_issue_transaction(this->upstream_target.map_target(),
                     &t, addr);
}
// }}
