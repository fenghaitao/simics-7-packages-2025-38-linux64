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

#include "simics/after.h"
#include "simics/after-interface.h"

#include <stdexcept>
#include <string>
#include <unordered_set>

namespace simics {

// AfterCall
void AfterCall::addIface(AfterCallInterface *iface) {
    if (iface == nullptr) {
        throw std::invalid_argument {
            "AfterCallInterface pointer cannot be nullptr"
        };
    } else {
        getIfaces().insert(iface);
    }
}

void AfterCall::removeIface(AfterCallInterface *iface) {
    if (iface == nullptr) {
        throw std::invalid_argument {
            "AfterCallInterface pointer cannot be nullptr"
        };
    } else {
        getIfaces().erase(iface);
    }
}

AfterCallInterface *AfterCall::findIface(const std::string &name) {
    if (name.empty()) {
        throw std::invalid_argument {
            "Empty name cannot be used to find AfterCallInterface"
        };
    }
    for (auto iface : getIfaces()) {
        if (iface->name() == name) {
            return iface;
        }
    }
    return nullptr;
}

std::unordered_set<AfterCallInterface*> &AfterCall::getIfaces() {
    static auto* ifaces = new std::unordered_set<AfterCallInterface*>();
    return *ifaces;
}

// AfterEvent
void AfterEvent::callback(void *data) {
    auto *iface = static_cast<AfterCallInterface *>(data);
    iface->invoke();
    delete iface;
}

attr_value_t AfterEvent::get_value(void *data) {
    auto *iface = static_cast<AfterCallInterface *>(data);
    return iface->get_value();
}

void *AfterEvent::set_value(attr_value_t value) {
    // The input value needs to be in format of [s[a*]] (a pair consists
    // of a string and a list of anything)
    checkSetValueFormat(value);
    std::string name {
        SIM_attr_string(SIM_attr_list_item(value, 0))
    };
    auto *iface = AfterCall::findIface(name);
    if (iface == nullptr) {
        SIM_LOG_ERROR(obj_->obj(), 0, "%s %s",
                      "Cannot find AfterInterface for function",
                      name.c_str());
        return nullptr;
    }
    // To support multiple after events with same name, a copy is needed
    auto *new_iface = iface->make_copy();
    new_iface->set_args(SIM_attr_list_item(value, 1));
    return new_iface;
}

void AfterEvent::remove(void *) const {
    if (clock_) {
        SIM_event_cancel_time(clock_, ev_, obj_->obj(), nullptr, nullptr);
    }
}

void AfterEvent::post(double seconds, void *data) {
    if (clock_ == nullptr) {
        /// clock_ is initialized when event is posted
        clock_ = SIM_object_clock(obj_->obj());
        if (clock_ == nullptr) {
            SIM_LOG_ERROR(obj_->obj(), 0,
                          "Queue not set, unable to post events");
            return;
        }
    }
    SIM_event_post_time(clock_, ev_, obj_->obj(), seconds, data);
    if (SIM_clear_exception() != SimExc_No_Exception) {
        SIM_LOG_ERROR(obj_->obj(), 0, "%s", SIM_last_error());
    }
}

void AfterEvent::post(cycles_t cycles, void *data) {
    if (clock_ == nullptr) {
        /// clock_ is initialized when event is posted
        clock_ = SIM_object_clock(obj_->obj());
        if (clock_ == nullptr) {
            SIM_LOG_ERROR(obj_->obj(), 0,
                          "Queue not set, unable to post events");
            return;
        }
    }
    SIM_event_post_cycle(clock_, ev_, obj_->obj(), cycles, data);
    if (SIM_clear_exception() != SimExc_No_Exception) {
        SIM_LOG_ERROR(obj_->obj(), 0, "%s", SIM_last_error());
    }
}

void AfterEvent::checkSetValueFormat(const attr_value_t &value) {
    // The input value needs to be in format of [s[*]] (a pair consists
    // of a string a a list of anything)
    if (!SIM_attr_is_list(value)
        || SIM_attr_list_size(value) != 2
        || !SIM_attr_is_string(SIM_attr_list_item(value, 0))
        || !SIM_attr_is_list(SIM_attr_list_item(value, 1))) {
        throw std::invalid_argument {
            "Invalid value to restore after event"
        };
    }
}

}  // namespace simics
