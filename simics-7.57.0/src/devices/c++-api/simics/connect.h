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

#ifndef SIMICS_CONNECT_H
#define SIMICS_CONNECT_H

#include <simics/base/log.h>  // SIM_LOG_INFO

#include <set>
#include <string>
#include <tuple>

#include "simics/conf-object.h"
#include "simics/detail/attribute-exceptions.h"  // InterfaceNotFound

namespace simics {

/**
 * A base class for Simics C++ interface connect class.
 *
 * The `ConnectBase` class provides common functionality for derived classes
 * that need to manage a connection to a Simics configuration object.
 */
class ConnectBase {
  public:
    ConnectBase() : obj_(nullptr) {}
    virtual ~ConnectBase() = default;

    /**
     * Set the connected configuration object.
     *
     * @param o The configuration object to connect.
     * @return True if the connection was successful, false otherwise.
     */
    virtual bool set(const ConfObjectRef &o) = 0;

    /**
     * Get the connected configuration object.
     *
     * @return The connected configuration object.
     */
    ConfObjectRef get() const { return obj_; }

    /**
     * Conversion operator to `conf_object_t*`.
     *
     * @return A pointer to the connected configuration object.
     */
    operator conf_object_t*() const { return obj_.object(); }

  protected:
    ConfObjectRef obj_;
};

/**
 * By default, all interfaces in the Connect class are required. Attempting to
 * connect an object that does not implement the required interfaces will cause
 * a runtime error. Use this class and pass it as CTOR param of Connect class
 * to make the interface check optional. Optional interfaces can be verified by
 * testing if the get_iface member of the interface has a nullptr value.
 */
class ConnectConfig {
  public:
    ConnectConfig() = default;

    bool is_optional(const std::string &iface_name) const {
        return optional_ifaces_.find(iface_name) \
            != optional_ifaces_.end();
    }

    template<typename FirstIface, typename... RestIfaces>
    static ConnectConfig optional() {
        ConnectConfig config;
        config.mark_optional<FirstIface, RestIfaces...>();
        return config;
    }

  private:
    template<typename T>
    void mark_optional() {
        optional_ifaces_.insert(typename T::Info().name());
    }

    // The variadic template
    template<typename FirstIface, typename... RestIfaces>
    typename std::enable_if<sizeof...(RestIfaces) != 0, void>::type
    mark_optional() {
        optional_ifaces_.insert(typename FirstIface::Info().name());
        mark_optional<RestIfaces...>();
    }

    std::set<std::string> optional_ifaces_;
};

/**
 * A class for connecting with another Simics object. The template
 * parameter(s) should be a group of Simics device interfaces, e.g,
 * simics::iface::SignalInterface.
 *
 * When method set is called, the Simics C interface pointers are fetched
 * and cached locally for performance reasons. Use method iface<T> when
 * invoking the Simics device interface method. For convenience, method iface
 * return the first Simics device interface.
 */
template<typename FirstIface, typename... RestIfaces>
class Connect : public ConnectBase {
  public:
    using ifaces_type = std::tuple<typename FirstIface::ToC,
                                   typename RestIfaces::ToC...>;
    Connect() = default;
    explicit Connect(const ConnectConfig &config) : config_(config) {}

    explicit Connect(const ConfObjectRef &device) : device_(device) {}
    Connect(const ConfObjectRef &device, const ConnectConfig &config)
        : device_(device), config_(config) {}

    // ConnectBase
    bool set(const ConfObjectRef &o) override {
        if (obj_ == o) {
            return true;
        }

        if (!o) {
            ifaces_ = ifaces_type();
            obj_ = o;
            return true;
        }

        try {
            set_ifaces<FirstIface, RestIfaces...>(o);
        } catch (const detail::SetInterfaceNotFound &e) {
            if (device_) {
                SIM_LOG_INFO(1, device_, 0, "%s", e.what());
            } else {
                SIM_LOG_INFO(1, SIM_get_object("sim"), 0, "%s", e.what());
            }
            ifaces_ = ifaces_type();
            return false;
        }

        obj_ = o;
        return true;
    }

    /**
     * Return the Simics C++ interface struct implemented on obj_.
     *
     * Check if this Connect is set before calling this method.
     * When this Connect is set, it is guaranteed that a valid
     * Simics C++ interface struct is returned.
     */
    template<typename T>
    typename std::enable_if<sizeof...(RestIfaces) != 0,
                            const typename T::ToC>::type
    iface() const {
        return std::get<typename T::ToC>(ifaces_);
    }

    const typename FirstIface::ToC &iface() const {
        return std::get<typename FirstIface::ToC>(ifaces_);
    }

  protected:
    /// Return the device object which can be used for logging purpose
    conf_object_t *device() const {
        if (device_ == nullptr) {
            SIM_LOG_ERROR(SIM_get_object("sim"), 0,
                          "Device is not set, should be set from the CTOR");
        }
        return device_;
    }

    /// Return the device object which can be used for logging purpose
    /// This is an alias for device() and follows the DML naming style
    conf_object_t *dev() const {
        return device();
    }

  private:
    template<typename T>
    const typename T::ctype *interface_(const ConfObjectRef &o) const {
        std::string iface_name = typename T::Info().name();
        auto iface = static_cast<const typename T::ctype *>(
                o.get_interface(iface_name));
        if (!iface && !config_.is_optional(iface_name)) {
            throw detail::SetInterfaceNotFound {
                "Interface " + iface_name + " not found in " + o.name()
            };
        }
        return iface;
    }

    template<typename T>
    void set_ifaces(const ConfObjectRef &o) {
        std::get<typename T::ToC>(ifaces_) = \
            typename T::ToC(o.object(), interface_<T>(o));
    }

    // The variadic template
    template<typename First, typename... Rest>
    typename std::enable_if<sizeof...(Rest) != 0, void>::type
    set_ifaces(const ConfObjectRef &o) {
        std::get<typename First::ToC>(ifaces_) = \
            typename First::ToC(o.object(), interface_<First>(o));
        set_ifaces<Rest...>(o);
    }

    ifaces_type ifaces_;
    conf_object_t *device_ {nullptr};
    ConnectConfig config_;
};

}  // namespace simics

#endif
