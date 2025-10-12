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

#include "simics/conf-object.h"

#include <simics/base/conf-object.h>
#include <simics/base/attr-value.h>  // SIM_attr_list_item

#include <stdexcept>
#include <string>

#include "simics/attr-value.h"
#include "simics/conf-class.h"
#include "simics/log.h"

namespace simics {

bool operator==(const ConfObjectRef &lhs, const ConfObjectRef &rhs) {
    return lhs.object() == rhs.object() && lhs.port_name() == rhs.port_name();
}
bool operator!=(const ConfObjectRef &lhs, const ConfObjectRef &rhs) {
    return !(lhs == rhs);
}

void *ConfObjectRef::data() const {
    return SIM_object_data(o_);
}

std::string ConfObjectRef::name() const {
    // The name may change if the object is moved to another hierarchical
    // location, cannot cache the return value here
    return SIM_object_name(o_);
}

void ConfObjectRef::require() const {
    SIM_require_object(o_);
}

bool ConfObjectRef::configured() const {
    return SIM_object_is_configured(o_);
}

conf_object_t *ConfObjectRef::port_obj_parent() const {
    return SIM_port_object_parent(o_);
}

ConfObject &ConfObjectRef::as_conf_object() const {
    auto *d = data();
    if (d == nullptr) {
        throw std::runtime_error {
            "The data pointer of the object(" + name() +
            ") is nullptr. Only valid after the init method is returned."
        };
    }
    return *static_cast<ConfObject*>(d);
}

const interface_t *ConfObjectRef::get_interface(const std::string &name) const {
    return SIM_c_get_port_interface(
            o_, name.c_str(),
            port_name_.empty() ? nullptr : port_name_.c_str());
}

uint64 ConfObjectRef::group_id(const std::string &name) const {
    SIM_LOG_WARNING(o_, 0,
                    "Using the ConfObjectRef::group_id function is deprecated,"
                    " use macro GROUP_ID or ConfClass::getGroupId instead");
    return ConfClass::getGroupId(SIM_object_class(o_), name);
}

#if defined INTC_EXT
void ConfObject::init_log_groups() {}
#endif

}  // namespace simics
