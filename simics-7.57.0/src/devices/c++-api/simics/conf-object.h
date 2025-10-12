// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_CONF_OBJECT_H
#define SIMICS_CONF_OBJECT_H

#include <simics/base/conf-object.h>
#include <simics/simulator/conf-object.h>

#include <cassert>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include "simics/conf-object-interface.h"

namespace simics {

class ConfObject;

/**
 * Represents Simics C type conf_object_t.
 *
 * @see conf_object_t
 */
class ConfObjectRef {
  public:
    /**
     * Not explicit constructor, allow conversion of conf_object_t to
     * ConfObjectRef
     *
     * @param obj The configuration object that will be represented by this
     * ConfObjectRef
     */
    ConfObjectRef(conf_object_t *obj = nullptr)  // NOLINT(runtime/explicit)
        : o_(obj) {}
    virtual ~ConfObjectRef() = default;

    //@{
    /// Get a pointer to the configuration object represented by this
    /// ConfObjectRef
    conf_object_t *object() const { return o_; }
    operator conf_object_t *() const { return o_; }
    //@}

    //@{
    /// Get & set name for the port implements the interface
    const std::string &port_name() const { return port_name_; }
    void set_port_name(const std::string &name) { port_name_ = name; }
    //@}

    /// Get the data of the underlying configuration object
    void *data() const;

    /// Get the name of the underlying configuration object
    std::string name() const;

    /// Ensure that the configuration object is instantiated (this is the same
    /// as calling SIM_require_object(object())
    void require() const;

    /// Return true if the configuration object is configured, false
    /// otherwise. This is the same as calling
    /// SIM_object_is_configured(object())
    bool configured() const;

    /// Return the parent object if the object is a port object, nullptr
    /// otherwise
    conf_object_t *port_obj_parent() const;

    /// Get a reference to the associated ConfObject
    ConfObject &as_conf_object() const;

    /**
     * Return an interface implemented by the underlying configuration
     * object. It is suggested to cache the result rather than do it
     * repeatedly to increase performance.
     *
     * @param name The name of the interface
     * @return A pointer to the interface struct, or nullptr if the interface
     * is not implemented by the underlying configuration object
     */
    const interface_t *get_interface(const std::string &name) const;

    [[deprecated("Use GROUP_ID or ConfClass::getGroupId instead")]]
    uint64 group_id(const std::string &name) const;

  private:
    conf_object_t *o_ {nullptr};
    /// Legacy support for Simics port interface
    std::string port_name_;
};

/**
 * @brief Compares two ConfObjectRef objects for equality.
 *
 * Two ConfObjectRef objects are considered equal if both their object()
 * and port_name() are same.
 */
bool operator==(const ConfObjectRef &lhs, const ConfObjectRef &rhs);
bool operator!=(const ConfObjectRef &lhs, const ConfObjectRef &rhs);

/**
 * @brief Base class for all Simics configuration objects.
 * 
 * Every device class that inherits from the ConfObject class, whether directly or indirectly,
 * can be registered as a Simics class. However, registration is not automatic; it requires
 * either the use of the RegisterWithSimics template class or the invocation of the make_class
 * template function.
 * 
 * Additionally, custom behavior that occurs after this object or all objects are finalized can
 * be implemented by overriding methods in the ConfObjectInterface.
 */
class ConfObject : public ConfObjectInterface {
  public:
    /// Create a ConfObject from ConfObjectRef
    explicit ConfObject(const ConfObjectRef &obj) : obj_(obj) {}
    virtual ~ConfObject() = default;

    // iface::ConfObjectInterface
    void finalize() override {}
    void objects_finalized() override {}

    /// Return a ConfObjectRef represents this object
    ConfObjectRef obj() const { return obj_; }

    /// Return if the finalize method has been called
    virtual bool finalized() {
        return SIM_object_is_configured(obj_);
    }

  private:
#if defined INTC_EXT
    [[deprecated("Dead function to maintain ABI compatibility with "
                 "Simics Base version 6.0.215")]]
    void init_log_groups();
#endif

    ConfObjectRef obj_;
#if defined INTC_EXT
    std::unordered_map<std::string, uint64> groups_;
#endif
};

/**
 * Utility function to convert a conf_object_t* to a pointer to C++
 * class derived from simics::ConfObject
 *
 * For performance reasons we cannot use dynamic_cast here, we should use
 * static_cast.
 * The static_assert makes it safe to use static_cast from void* to T*.
 * The intermediate static_cast from void* to ConfObject* avoids undefined
 * behavior if the conf-object data points to a class that does not have
 * ConfObject as first base class.
 */
template <typename T> inline
T *from_obj(conf_object_t *obj) {
    static_assert(std::is_base_of<ConfObject, T>::value,
                  "type T is not derived from type ConfObject");
    auto *d = static_cast<ConfObject *>(SIM_object_data(obj));
    assert(d);
    return static_cast<T*>(d);
}

}  // namespace simics
#endif
