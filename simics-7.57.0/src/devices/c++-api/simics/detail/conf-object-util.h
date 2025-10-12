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

#ifndef SIMICS_DETAIL_CONF_OBJECT_UTIL_H
#define SIMICS_DETAIL_CONF_OBJECT_UTIL_H

#include <stdexcept>  // runtime_error

#include "simics/conf-object.h"

namespace simics {
namespace detail {

/**
 * Return the Simics C++ interface class from a configuration object.
 */
template <typename IFACE>
IFACE* get_interface(conf_object_t *obj) {
    // See bug 21722, the performance benchmark shows dynamic_cast
    // is better than cache it by a map
    auto *iface = dynamic_cast<IFACE*>(from_obj<ConfObject>(obj));
    if (!iface) {
        throw std::runtime_error {
            "The configuration object needs derive from the interface class"
        };
    }
    return iface;
}

}  // namespace detail
}  // namespace simics

#endif
