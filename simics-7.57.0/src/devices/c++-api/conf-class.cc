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

#include "simics/conf-class.h"

#include <simics/base/log.h>  // SIM_LOG_XXX
#include <simics/base/conf-object.h>  // SIM_get_class_data
#include <simics/base/sim-exception.h>  // SIM_clear_exception

#include <algorithm>
#include <cassert>
#include <functional>  // std::hash
#include <memory>
#include <stdexcept>  // runtime_error
#include <string>
#include <unordered_map>
#include <utility>  // std::pair
#include <vector>

#include "simics/conf-object.h"
#include "simics/object-factory-interface.h"
#include "simics/utility.h"  // expand_names

namespace simics {

// A function called when creating an instance of the class.
// The C++ device object is created
static void *init(conf_object_t *obj) {
    auto *factory = static_cast<ObjectFactoryInterface*>(
            SIM_get_class_data(SIM_object_class(obj)));
    assert(factory);

    try {
        return factory->create(obj);
    } catch(const std::exception &e) {
        SIM_LOG_INFO(1, obj, 0, "%s", e.what());
    } catch(...) {
        SIM_LOG_INFO(1, obj, 0, "%s",
                     "Unknown C++ exception during object construction.");
    }

    return nullptr;
}

// A function called when init has returned, and all attributes
// in a configuration has been set. It calls the finalize method
// on the created C++ object
static void finalize(conf_object_t *obj) {
    ConfObjectRef r(obj);
    r.as_conf_object().finalize();
}

// A function called after finalize has been called on all objects,
// so in this method the configuration is ready, and communication
// with other objects is permitted without restrictions. It calls
// the objects_finalized method on the created C++ object
static void objects_finalized(conf_object_t *obj) {
    ConfObjectRef r(obj);
    r.as_conf_object().objects_finalized();
}

// A function called first when the object is being deleted.
// The created C++ device object is destroyed
static void deinit(conf_object_t *obj) {
    delete from_obj<ConfObject>(obj);
}

/**
 * Create, register and return a Simics class
 *
 * @see conf_class_t
 * @param name the registered class name
 * @param short_desc a short description of the class, preferably a one-line
 * @param description a longer description of the class
 * @param kind an enum determine if the configuration object should be saved
 *             when a checkpoint is created.
 * @return pointer of created class
 */
static conf_class_t *create_conf_class(const std::string &name,
                                       const std::string &short_desc,
                                       const std::string &description,
                                       const class_kind_t kind) {
    class_info_t info {};
    info.init = init;
    info.finalize = finalize;
    info.objects_finalized = objects_finalized;
    info.deinit = deinit;
    info.kind = kind;

    // The char pointer is only used by SIM_create_class and
    // there it is deep copied inside.
    info.description = description.c_str();
    info.short_desc = short_desc.c_str();
    return SIM_create_class(name.c_str(), &info);
}

// Custom hash function for std::pair<conf_class_t*, std::string>
struct PairHash {
    std::size_t operator()(const std::pair<conf_class_t*,
                           std::string>& p) const {
        auto hash1 = std::hash<conf_class_t*>{}(p.first);
        auto hash2 = std::hash<std::string>{}(p.second);
        return hash1 ^ (hash2 << 1);
    }
};

// Custom equality function for std::pair<conf_class_t*, std::string>
struct PairEqual {
    bool operator()(const std::pair<conf_class_t*, std::string>& lhs,
                    const std::pair<conf_class_t*, std::string>& rhs) const {
        return lhs.first == rhs.first && lhs.second == rhs.second;
    }
};

static std::unordered_map<std::pair<conf_class_t *, std::string>,
                          uint64, PairHash, PairEqual>& getCachedGroupId() {
    // This ensures that the variable is initialized the first time the function
    // is called
    static std::unordered_map<std::pair<conf_class_t *, std::string>,
                              uint64, PairHash, PairEqual> cached_group_id {};
    return cached_group_id;
}

// ConfClass methods
ConfClass::~ConfClass() {
    // The registration of log groups cannot be done in cls->add since
    // SIM_log_register_groups can only be called once per conf_class_t
    register_log_groups();
    // The registration of interfaces is done here to allow overwriting
    register_interfaces();
}

ConfClassPtr ConfClass::createInstance(
        const std::string &name,
        const std::string &short_desc,
        const std::string &description,
        const class_kind_t kind,
        const ObjectFactoryInterface &factory) {
    // Return nullptr when failed creating class
    conf_class_t *cls = create_conf_class(name, short_desc,
                                          description, kind);
    if (!cls) {
        throw std::runtime_error { "Failed to create class " + name };
    }

    // Should live as long as the conf_class_t cls
    auto *cls_data = static_cast<void*>(factory.clone());
    SIM_set_class_data(cls, cls_data);
    VT_set_constructor_data(cls, cls_data);

    // make_unique not working with protected ctor
    return ConfClassPtr(new ConfClass(cls, name, description));
}

#if defined INTC_EXT
// to maintain ABI compatibility with Simics Base version 6.0.215
ConfClassPtr ConfClass::createInstance(
            const std::string &name,
            const std::string &short_desc,
            const std::string &description,
            const class_kind_t kind,
            const iface::ObjectFactoryInterface &factory) {
    return createInstance(name, short_desc, description, kind,
                          static_cast<const ObjectFactoryInterface &>(factory));
}
#endif

uint64 ConfClass::getGroupId(conf_class_t *cls, const std::string &name) {
    auto &cached_group_id = getCachedGroupId();
    auto it = cached_group_id.find(std::make_pair(cls, name));
    if (it != cached_group_id.end()) {
        return it->second;
    } else {
        SIM_LOG_ERROR(SIM_get_object("sim"), 0, "%s",
                      ("Undefined log group " + name).c_str());
        return 0;
    }
}

ConfClass::operator conf_class_t*() const {
    return cls_;
}

const std::string &ConfClass::name() const {
    return name_;
}

const std::string &ConfClass::description() const {
    return description_;
}

const std::vector<std::string> &ConfClass::log_groups() const {
    return log_groups_;
}

ConfClass *ConfClass::add(const iface::InterfaceInfo &iface) {
    if (iface.cstruct() == nullptr) {
        SIM_LOG_ERROR(SIM_get_object("sim"), 0,
                      "Invalid InterfaceInfo (cstruct() returns NULL)");
        return this;
    }
    pending_interfaces_[iface.name()] = iface.cstruct();
    return this;
}

ConfClass *ConfClass::add(const Attribute &attr) {
    SIM_register_attribute(cls_, attr.name().c_str(),
                           attr.getter(), attr.setter(),
                           attr.attr(), attr.type().c_str(),
                           attr.desc().c_str());
    return this;
}

ConfClass *ConfClass::add(const ClassAttribute &attr) {
    SIM_register_class_attribute(cls_, attr.name().c_str(),
                                 attr.getter(), attr.setter(),
                                 attr.attr(), attr.type().c_str(),
                                 attr.desc().c_str());
    return this;
}

ConfClass *ConfClass::add(const char * const *names) {
    if (names != nullptr) {
        size_t index = 0;
        while (names[index] != nullptr) {
            if (log_groups_.size() == 63) {
                throw std::runtime_error {
                    "Maximum number of 63 user-defined log groups exceeded"
                };
            }
            log_groups_.push_back(names[index++]);
        }
    }
    return this;
}

ConfClass *ConfClass::add(const LogGroups &names) {
    if (log_groups_.size() + names.size() > 63) {
        throw std::runtime_error {
            "Maximum number of 63 user-defined log groups exceeded"
        };
    }
    log_groups_.insert(log_groups_.end(), names);
    return this;
}

ConfClass *ConfClass::add(ConfClass *port, const std::string &name) {
    // Array like name is expanded and each is registered as a port
    for (const auto &s : expand_names(name)) {
        SIM_register_port(cls_, s.c_str(), *port,
                          port->description().c_str());
    }
    return this;
}

ConfClass *ConfClass::add(const ConfClassPtr &port, const std::string &name) {
    return add(port.get(), name);
}

ConfClass *ConfClass::add(EventInfo &&event) {
    event_class_t *event_class = SIM_register_event(
        event.name.c_str(), *this,
        event.flags,
        event.callback, event.destroy,
        event.get_value, event.set_value,
        event.describe);

    if (event_class == nullptr) {
        throw std::runtime_error {
            "Failed to register event " + event.name
        };
    }

    if (event.ev) {
        *event.ev = event_class;
    }

    return this;
}

void ConfClass::register_log_groups() const noexcept {
    if (log_groups_.empty()) {
        // No log groups to register
        return;
    }

    auto &cached_group_id = getCachedGroupId();
    const char *names[64] {nullptr};
    size_t index = 0;
    for (const auto &name : log_groups_) {
        cached_group_id[std::make_pair(cls_, name)] = 1ULL << index;
        names[index++] = name.c_str();
    }

    SIM_log_register_groups(cls_, names);
    // SIM_log_register_groups may raise exception
    // for example, when being invoked more than once
    if (SIM_clear_exception() != SimExc_No_Exception) {
        SIM_LOG_ERROR(SIM_get_object("sim"), 0, "%s", SIM_last_error());
    }
}

void ConfClass::register_interfaces() noexcept {
    for (const auto& entry : pending_interfaces_) {
        const auto& name = entry.first;
        const auto& iface = entry.second;
        int fail = SIM_register_interface(cls_, name.c_str(), iface);
        if (fail) {
            // Use (void) to avoid coverity warning "unchecked_return_value"
            (void)SIM_clear_exception();
            SIM_LOG_ERROR(SIM_get_object("sim"), 0,
                          "Failed to add info for interface '%s': %s",
                          name.c_str(), SIM_last_error());
        }
    }
    pending_interfaces_.clear();
}

}  // namespace simics
