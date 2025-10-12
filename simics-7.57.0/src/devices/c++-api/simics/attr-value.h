// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_ATTR_VALUE_H
#define SIMICS_ATTR_VALUE_H

#include <simics/base/attr-value.h>

#include <utility>

namespace simics {

/*
 * RAII class holding a Simics attr_value_t
 *
 * Construct the class from Simics API call which returns
 * a attr_value_t, e.g, SIM_get_attribute, SIM_attr_copy.
 * When desctructed, it frees the memory allocation used by
 * the attr_value_t.
 */
class AttrValue {
  public:
    explicit AttrValue(attr_value_t &&attr) : attr_(std::move(attr)) {}

    AttrValue(const AttrValue&) = delete;
    AttrValue& operator=(const AttrValue &) = delete;
    AttrValue(AttrValue &&rhs) noexcept : attr_(std::move(rhs.attr_)) {
        rhs.attr_.private_kind = Sim_Val_Invalid;
    }
    AttrValue &operator=(AttrValue &&rhs) noexcept {
        if (this != &rhs) {
            SIM_attr_free(&attr_);
            attr_ = std::move(rhs.attr_);
            rhs.attr_.private_kind = Sim_Val_Invalid;
        }
        return *this;
    }
    ~AttrValue() {
        SIM_attr_free(&attr_);
    }

    operator attr_value_t &() { return attr_; }

    // Assignment operator from rvalue attr_value_t
    AttrValue &operator=(attr_value_t &&rhs) noexcept {
        SIM_attr_free(&attr_);
        attr_ = std::move(rhs);
        rhs.private_kind = Sim_Val_Invalid;
        return *this;
    }

  private:
    attr_value_t attr_;
};

}  // namespace simics


#endif
