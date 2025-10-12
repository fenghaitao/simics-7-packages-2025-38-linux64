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

#ifndef SIMICS_CC_MODELING_API_H
#define SIMICS_CC_MODELING_API_H

#ifndef DISABLE_WARNING_ON_TECH_PREVIEW
#pragma message("You are using the C++ modeling library which is currently a" \
" tech-preview feature. To disable this warning define" \
" DISABLE_WARNING_ON_TECH_PREVIEW")
#endif

#if defined _MSVC_LANG
#if _MSVC_LANG < 201703L
#error "The C++ compiler version is not supported" \
    " (C++ API bank register extension requires C++17)"
#endif
#elif defined __cplusplus
#if __cplusplus < 201703L
#error "The C++ compiler version is not supported" \
    " (C++ API bank register extension requires C++17)"
#endif
#endif

#include "simics/after-bank.h"
#include "simics/bank.h"
#include "simics/bank-templates.h"
#include "simics/bank-port.h"
#include "simics/field.h"
#include "simics/field-templates.h"
#include "simics/mappable-conf-object.h"
#include "simics/register.h"
#include "simics/register-templates.h"

// For backwards compatibility, include simics::iface::XxxInterface
#if defined SIMICS_6_API || defined SIMICS_7_API
#include "simics/iface/bank-interface.h"
#include "simics/iface/bank-issue-callbacks-interface.h"
#include "simics/iface/bank-port-interface.h"
#include "simics/iface/field-interface.h"
#include "simics/iface/hierarchical-object-interface.h"
#include "simics/iface/map-name-to-interface.h"
#include "simics/iface/register-interface.h"
#include "simics/iface/value-accessor-interface.h"
#include "simics/iface/value-mutator-interface.h"
#endif

#endif

