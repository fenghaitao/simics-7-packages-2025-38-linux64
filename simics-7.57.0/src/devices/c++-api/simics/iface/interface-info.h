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

#ifndef SIMICS_IFACE_INTERFACE_INFO_H
#define SIMICS_IFACE_INTERFACE_INFO_H

#include <string>

// Repeat the definition to avoid including simics/base/conf-object.h
typedef void interface_t;

namespace simics {
namespace iface {

class InterfaceInfo {
  public:
    virtual ~InterfaceInfo() = default;
    virtual std::string name() const = 0;
    virtual const interface_t *cstruct() const = 0;
};

}  // namespace iface
}  // namespace simics

#endif
