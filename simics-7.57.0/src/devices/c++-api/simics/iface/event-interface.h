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

#ifndef SIMICS_IFACE_EVENT_INTERFACE_H
#define SIMICS_IFACE_EVENT_INTERFACE_H

#if defined SIMICS_6_API || defined SIMICS_7_API

#include "simics/event-interface.h"

namespace simics {
namespace iface {

using EventInterface
[[deprecated("Use simics::EventInterface instead")]] = \
    simics::EventInterface;
using TimeEventInterface
[[deprecated("Use simics::TimeEventInterface instead")]] = \
    simics::TimeEventInterface;

// SIMICS-22961, no alias of simics::iface::CycleEventInterface to
// simics::CycleEventInterface. User must use simics::CycleEventInterface
// to avoid possible name collision

using StepEventInterface
[[deprecated("Use simics::StepEventInterface instead")]] = \
    simics::StepEventInterface;

}  // namespace iface
}  // namespace simics

#endif
#endif
