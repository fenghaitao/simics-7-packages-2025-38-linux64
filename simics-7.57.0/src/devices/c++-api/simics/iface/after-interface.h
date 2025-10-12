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

#ifndef SIMICS_IFACE_AFTER_INTERFACE_H
#define SIMICS_IFACE_AFTER_INTERFACE_H

#if defined SIMICS_6_API || defined SIMICS_7_API

#include "simics/after-interface.h"

namespace simics {
namespace iface {

using AfterCallInterface
[[deprecated("Use simics::AfterCallInterface instead")]] = \
    simics::AfterCallInterface;
using AfterInterface
[[deprecated("Use simics::AfterInterface instead")]] = \
    simics::AfterInterface;

}  // namespace iface
}  // namespace simics

#endif
#endif
