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

#ifndef SIMICS_LOG_H
#define SIMICS_LOG_H

#include <simics/base/log.h>  // SIM_LOG_XXX

#include <initializer_list>
#include <string>

namespace simics {

/// Type used for log group names
using LogGroups = std::initializer_list<std::string>;

/// Special macro to handle string object (for example, fmt::format)
#define SIM_LOG_INFO_STR(level, obj, group, str)        \
    SIM_LOG_INFO(level, obj, group, "%s", str.c_str())

#define SIM_LOG_SPEC_VIOLATION_STR(level, obj, group, str)        \
    SIM_LOG_SPEC_VIOLATION(level, obj, group, "%s", str.c_str())

#define SIM_LOG_UNIMPLEMENTED_STR(level, obj, group, str)        \
    SIM_LOG_UNIMPLEMENTED(level, obj, group, "%s", str.c_str())

#define SIM_LOG_ERROR_STR(obj, group, str)          \
    SIM_LOG_ERROR(obj, group, "%s", str.c_str())

#define SIM_LOG_CRITICAL_STR(obj, group, str)          \
    SIM_LOG_CRITICAL(obj, group, "%s", str.c_str())

#define SIM_LOG_WARNING_STR(obj, group, str)          \
    SIM_LOG_WARNING(obj, group, "%s", str.c_str())

}  // namespace simics

#endif
