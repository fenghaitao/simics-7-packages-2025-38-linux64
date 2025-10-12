// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_MAPPABLE_CONF_OBJECT_H
#define SIMICS_MAPPABLE_CONF_OBJECT_H

#include <simics/base/log.h>  // SIM_LOG_ERROR

#include <stdexcept>
#include <string>
#include <string_view>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

#include "simics/conf-object.h"
#include "simics/map-name-to-interface.h"
#include "simics/type/bank-type.h"
#include "simics/utility.h"  // hash_str

namespace simics {

/**
 * @brief Class that supports get/set a pointer to IFACE with a string name.
 *
 * The MapNameToInterfaceObject class provides functionality to map names
 * to interface objects. It allows setting, getting, and erasing interfaces
 * by their names. This class is used to manage associations between names
 * and interface objects in a structured manner.
 *
 * @tparam IFACE The type of the interface.
 */
template <typename IFACE>
class MapNameToInterfaceObject : public MapNameToInterface<IFACE> {
  public:
    /**
     * @brief Sets the IFACE associated with the given name.
     *
     * This function associates the given IFACE with the specified name.
     * If the interface is null or the name is empty, it throws an invalid_argument
     * exception.
     *
     * @param name The name to associate with the IFACE.
     * @param iface The IFACE to associate with the name.
     * @throws std::invalid_argument if the interface is null or the name is empty.
     */
    void set_iface(const std::string &name, IFACE *iface) override {
        if (!iface) {
            throw std::invalid_argument {
                "Cannot set with NULL interface"
            };
        } else if (name.empty()) {
            throw std::invalid_argument {
                "Cannot set with empty name string"
            };
        } else {
            name_to_iface_[hash_str(name)] = iface;
        }
    }

    /**
     * @brief Gets the interface associated with the given name.
     *
     * This function retrieves the interface associated with the specified name.
     * If no interface is found for the given name, it returns nullptr.
     *
     * @param name The name associated with the interface.
     * @return The interface associated with the name, or nullptr if not found.
     */
    IFACE *get_iface(std::string_view name) const override {
        return get_iface(hash_str(name));
    }

    /**
     * @brief Gets the interface associated with the given name hash.
     *
     * This function retrieves the interface associated with the specified name hash.
     * If no interface is found for the given hash, it returns nullptr.
     *
     * @param name_hash The hash value of the name associated with the interface.
     * @return The interface associated with the name hash, or nullptr if not found.
     */
    IFACE *get_iface(size_t name_hash) const {
        auto it = name_to_iface_.find(name_hash);
        if (it == name_to_iface_.end()) {
            return nullptr;
        }
        return it->second;
    }

    /**
     * @brief Erases the interface associated with the given name.
     *
     * This function removes the association between the specified name and
     * its interface. If no association exists for the given name, it does nothing.
     *
     * @param name The name associated with the interface to erase.
     */
    void erase_iface(const std::string &name) override {
        name_to_iface_.erase(hash_str(name));
    }

  private:
    /// Internal map to store the associations between names and interfaces.
    std::unordered_map<size_t, IFACE *> name_to_iface_;
};

class BankInterface;
class RegisterInterface;
class FieldInterface;

/*
 * A class extends ConfObject to support memory mapped bank registers
 *
 * It manages a container which associates a unique name to its corresponding
 * operational interface. These 3 object types are supported: bank, register
 * and field.
 */
class MappableConfObject : public ConfObject {
  public:
    using ConfObject::ConfObject;
    virtual ~MappableConfObject() = default;

    /// @brief Set the IFACE interface* by name
    /// @tparam IFACE should be one of BankInterface, RegisterInterface,
    ///               FieldInterface
    /// @param name The name of a hierarchical object
    /// @param iface the IFACE pointer to the hierarchical object
    template <typename IFACE>
    void set_iface(const std::string &name, IFACE *iface) {
        if (finalized()) {
            SIM_LOG_ERROR(obj(), 0,
                          "Cannot set interface for %s when ConfObject"
                          " has been finalized", name.c_str());
            return;
        }

        auto current_iface = get_iface<IFACE>(name);
        if (current_iface && current_iface != iface) {
            if (iface_maps_write_protected_) {
                SIM_LOG_INFO(3, obj(), 0,
                             "Interface for %s ignored since iface_map is"
                             " write protected", name.c_str());
                return;
            }
            SIM_LOG_INFO(4, obj(), 0,
                         "Interface for %s overridden", name.c_str());
        }

        try {
            std::get<MapNameToInterfaceObject<IFACE>>(
                    iface_maps_).set_iface(name, iface);
        } catch (const std::exception &e) {
            SIM_LOG_ERROR(obj(), 0, "%s", e.what());
        }
    }

    /// @brief Get the IFACE interface* by name
    /// @tparam IFACE should be one of BankInterface, RegisterInterface,
    ///               FieldInterface
    /// @param name The name of a hierarchical object
    /// @return The IFACE pointer to the hierarchical object.
    ///         It may return nullptr. Check NULL before use the return value.
    template <typename IFACE>
    IFACE *get_iface(std::string_view name) const {
        return std::get<MapNameToInterfaceObject<IFACE>>(
                iface_maps_).get_iface(name);
    }

    /// @brief Get the RegisterInterface* by name hash
    /// @param name_hash The hash value of the name of a hierarchical object
    /// @return The RegisterInterface pointer to the hierarchical object.
    RegisterInterface *get_iface(size_t name_hash) const {
        return std::get<MapNameToInterfaceObject<RegisterInterface>>(
                iface_maps_).get_iface(name_hash);
    }

    /// @brief Erase the IFACE interface by name
    /// @tparam IFACE should be one of BankInterface, RegisterInterface,
    ///               FieldInterface
    /// @param name The name of a hierarchical object
    template <typename IFACE>
    void erase_iface(const std::string &name) {
        std::get<MapNameToInterfaceObject<IFACE>>(
                iface_maps_).erase_iface(name);
    }

    // Whether to represent the bits in big endian, i.e, whether the bit
    // number 0 refers to the most significant bit.
    virtual bool big_endian_bitorder() {
        return false;
    }

    /// @brief Get the bank memory by name
    bank_memory_t *get_bank_memory(std::string_view name_of_memory) {
        return &allocated_bank_memories_[name_of_memory.data()];
    }

    /// Whether to write protect the iface_maps, default is not write protected
    void write_protect_iface_maps(bool write_protect) {
        iface_maps_write_protected_ = write_protect;
    }

  private:
    /// @internal tracks the name to interface associations
    std::tuple<MapNameToInterfaceObject<BankInterface>,
               MapNameToInterfaceObject<RegisterInterface>,
               MapNameToInterfaceObject<FieldInterface>> iface_maps_;

    /*
     * The allocated_bank_memories_ maps a string key to a
     * value of type bank_memory_t.
     *
     * This structure groups bytes memory for all banks, can be used
     * to efficiently store and access byte-level data using the name
     * and byte offset as keys.
     *
     * By default, each bank uses its bank name as the key to get the
     * bank memory. For SharedMemoryBank, multiple banks can share the
     * same bank memory by using the same key. The key can be any unique
     * string.
     */
    std::unordered_map<std::string,
                       bank_memory_t> allocated_bank_memories_;

    /// If the iface_maps is write protected
    bool iface_maps_write_protected_ {false};
};

}  // namespace simics

#endif
