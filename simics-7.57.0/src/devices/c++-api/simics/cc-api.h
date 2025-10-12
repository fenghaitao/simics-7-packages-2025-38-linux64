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

#ifndef SIMICS_CC_API_H
#define SIMICS_CC_API_H

#if defined _MSVC_LANG
#if _MSVC_LANG < 201402L
#error "The C++ compiler version is not supported (C++ API v2 requires C++14)"
#endif
#elif defined __cplusplus
#if __cplusplus < 201402L
#error "The C++ compiler version is not supported (C++ API v2 requires C++14)"
#endif
#endif

#include <simics/device-api.h>

#include "simics/after.h"
#include "simics/attribute.h"
#include "simics/conf-class.h"
#include "simics/conf-object.h"
#include "simics/connect.h"
#include "simics/connect-templates.h"
#include "simics/event.h"
#include "simics/iface/interface-info.h"
#include "simics/log.h"
#include "simics/port.h"
#include "simics/utility.h"

// For backwards compatibility, include simics::iface::XxxInterface
#if defined SIMICS_6_API || defined SIMICS_7_API
#include "simics/iface/after-interface.h"
#include "simics/iface/conf-object-interface.h"
#include "simics/iface/event-interface.h"
#include "simics/iface/object-factory-interface.h"
#endif

#endif
