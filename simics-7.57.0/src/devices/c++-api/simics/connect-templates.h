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

#ifndef SIMICS_CONNECT_TEMPLATES_H
#define SIMICS_CONNECT_TEMPLATES_H

#include <fmt/fmt/format.h>
#include <simics/base/map-target.h>
#include <simics/base/sim-exception.h>  // SIM_clear_exception
#include <simics/base/transaction.h>

#include <string>
#include <vector>

#include "simics/conf-object.h"
#include "simics/connect.h"
#include "simics/detail/attribute-exceptions.h"  // InterfaceNotFound
#include "simics/log.h"

namespace simics {

// A Connect default connects to its descendant
template<typename FirstIface, typename... RestIfaces>
class ConnectToDescendant: public Connect<FirstIface, RestIfaces...> {
  public:
    ConnectToDescendant(const ConfObject *device,
                        const std::string &descendant)
        : Connect<FirstIface, RestIfaces...>(device->obj()) {
        const ConfObjectRef dev_obj = device->obj();
        // Port must be registered using SIM_register_port
        if (!SIM_class_port(SIM_object_class(dev_obj), descendant.c_str())) {
            SIM_LOG_CRITICAL_STR(dev_obj, 0,
                                 fmt::format("Port {} is not registered yet",
                                             descendant));
            return;
        }

        conf_object_t *obj = SIM_object_descendant(dev_obj,
                                                   descendant.c_str());
        if (obj) {
            Connect<FirstIface, RestIfaces...>::set(obj);
        } else {
            SIM_LOG_INFO_STR(3, dev_obj, 0,
                             fmt::format("Descendant object {} not found",
                                         descendant));
        }
    }
};

/*
 * A map target can be viewed as an opaque representation of an
 * object/interface pair which can function either as an endpoint for a memory
 * transaction or as an address space where a memory transaction can be
 * performed.
 *
 * The interfaces are tried in the order of on the object:
 * ram, rom, io_memory, port_space, translator, transaction_translator,
 * transaction and memory_space
 */
class MapTarget {
  public:
    explicit MapTarget(const ConfObjectRef &device) : device_(device) {}
    virtual ~MapTarget()  {
        SIM_free_map_target(map_target_);
    }

    bool set_map_target(const ConfObjectRef &obj) {
        SIM_free_map_target(map_target_);
        if (!obj) {
            map_target_ = nullptr;
            return true;
        }

        map_target_t *tmp = SIM_new_map_target(obj, nullptr, nullptr);
        if (tmp == nullptr) {
            (void)SIM_clear_exception();
            throw detail::SetInterfaceNotFound {SIM_last_error()};
            return false;
        }
        map_target_ = tmp;
        return true;
    }

    uint64_t read(uint64_t addr, uint64_t size) {
        if (size > 8) {
            SIM_LOG_ERROR(device_, 0, "size must be less than or equal to 8");
            return 0;
        }
        std::vector<uint8_t> val(size);
        std::vector<atom_t> atoms {
            ATOM_data(val.data()),
            ATOM_size(size),
            ATOM_initiator(device_),
            ATOM_list_end(0)
        };
        transaction_t t {};
        t.atoms = atoms.data();
        auto exc = issue(&t, addr);
        if (exc != Sim_PE_No_Exception) {
            SIM_LOG_ERROR_STR(device_, 0,
                              fmt::format("unexpected exception: {}",
                                          static_cast<int>(exc)));
            return 0;
        }
        return SIM_get_transaction_value_le(&t);
    }

    void read_bytes(uint64_t addr, uint64_t size, uint8_t *bytes) {
        std::vector<atom_t> atoms {
            ATOM_data(bytes),
            ATOM_size(size),
            ATOM_initiator(device_),
            ATOM_list_end(0),
        };
        transaction_t t {};
        t.atoms = atoms.data();
        issue(&t, addr);
    }

    void write(uint64_t addr, uint64_t size, uint64_t value) {
        if (size > 8) {
            SIM_LOG_ERROR(device_, 0, "size must be less than or equal to 8");
            return;
        }
        std::vector<uint8_t> buf(size);
        std::vector<atom_t> atoms {
            ATOM_data(buf.data()),
            ATOM_size(size),
            ATOM_flags(Sim_Transaction_Write),
            ATOM_initiator(device_),
            ATOM_list_end(0)
        };
        transaction_t t {};
        t.atoms = atoms.data();
        SIM_set_transaction_value_le(&t, value);
        issue(&t, addr);
    }

    void write_bytes(uint64_t addr, uint64_t size, uint8_t *bytes) {
        std::vector<atom_t> atoms {
            ATOM_flags(Sim_Transaction_Write),
            ATOM_data(bytes),
            ATOM_size(size),
            ATOM_initiator(device_),
            ATOM_list_end(0),
        };
        transaction_t t {};
        t.atoms = atoms.data();
        issue(&t, addr);
    }

    exception_type_t issue(transaction_t *t, uint64_t addr) {
        if (t == nullptr) {
            SIM_LOG_INFO(2, device_, 0,
                         "null transaction is terminated");
            return Sim_PE_IO_Not_Taken;
        }

        if (!map_target_) {
            SIM_LOG_INFO(2, device_, 0,
                         "map_target not set, transaction terminated");
            return Sim_PE_IO_Not_Taken;
        }

        exception_type_t exc = SIM_issue_transaction(map_target_, t, addr);
        std::string op {SIM_transaction_is_read(t) ? "read" : "write"};
        if (exc == Sim_PE_No_Exception) {
            SIM_LOG_INFO_STR(4, device_, 0,
                             fmt::format("{} {} bytes @0x{:x} in {}",
                                         op, SIM_transaction_size(t),
                                         addr, SIM_object_name(device_)));
        } else {
            SIM_LOG_INFO_STR(2, device_, 0,
                             fmt::format("failed to {} {} bytes @0x{:x} in {}",
                                         op, SIM_transaction_size(t),
                                         addr, SIM_object_name(device_)));
        }
        return Sim_PE_No_Exception;
    }

    const map_target_t *map_target() const {
        return map_target_;
    }

  private:
    conf_object_t *device_ {nullptr};
    map_target_t *map_target_ {nullptr};
};

class MapTargetConnect : public ConnectBase, public MapTarget {
  public:
    explicit MapTargetConnect(const ConfObjectRef &device)
        : MapTarget(device) {}

    // ConnectBase
    bool set(const ConfObjectRef &o) override {
        bool success = MapTarget::set_map_target(o);
        if (success) {
            obj_ = o;
        }
        return success;
    }
};

}  // namespace simics

#endif
