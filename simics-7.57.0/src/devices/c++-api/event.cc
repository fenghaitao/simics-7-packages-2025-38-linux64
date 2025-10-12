// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2025 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "simics/event.h"

#include <string>

namespace simics {

EventInfo::EventInfo(const std::string &name, event_class_flag_t flags,
                     event_class_t **ev, ev_callback callback,
                     ev_destroy destroy, ev_value_getter get_value,
                     ev_value_setter set_value, ev_describe describe)
    : name(name), flags(flags), ev(ev), callback(callback),
      destroy(destroy), get_value(get_value), set_value(set_value),
      describe(describe) {
    if (name.empty()) {
        throw std::invalid_argument {
            "Event name cannot be empty"
        };
    }
    if (callback == nullptr) {
        throw std::invalid_argument {
            "Callback function for event " + name + " is missing"
        };
    }
    if ((flags & Sim_EC_Notsaved)
        && (get_value != nullptr || set_value != nullptr)) {
        throw std::invalid_argument {
            "Event '" + name + "' with Sim_EC_Notsaved flag must not have"
            + " get_value or set_value callbacks"
        };
    }
}

EventInfo::EventInfo(const std::string &name, event_class_t **ev,
                     ev_callback callback)
    : EventInfo(name, Sim_EC_No_Flags, ev, callback,
                nullptr, nullptr, nullptr, nullptr) {
}

Event::Event(ConfObject *obj, event_class_t *ev) : obj_(obj), ev_(ev) {
    if (obj == nullptr) {
        throw std::invalid_argument {
            "Device object can't be NULL"
        };
    }

    if (ev == nullptr) {
        throw std::invalid_argument {
            "Event is not registered yet. Call add() from the"
            " device class"
        };
    }
}

Event::Event(ConfObject *obj, const std::string &name) : obj_(obj) {
    if (obj == nullptr) {
        throw std::invalid_argument {
            "Device object can't be NULL"
        };
    }

    if (name.empty()) {
        throw std::invalid_argument {
            "Event name cannot be empty"
        };
    }

    ev_ = SIM_get_event_class(SIM_object_class(obj->obj()), name.c_str());
    if (ev_ == nullptr) {
        throw std::invalid_argument {
            "Event '" + name + "' is not registered"
        };
    }
}

void Event::destroy(void *data) {}

attr_value_t Event::get_value(void *data) {
    return SIM_make_attr_nil();
}

void *Event::set_value(attr_value_t value) {
    return nullptr;
}

char *Event::describe(void *data) const {
    return nullptr;
}

Event::operator event_class_t *() const {
    return ev_;
}

int Event::pointer_eq(void *data, void *match_data) {
    return data == match_data;
}

const char *Event::name() const {
    return ev_->name;
}

}  // namespace simics
