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

#ifndef SIMICS_AFTER_INTERFACE_H
#define SIMICS_AFTER_INTERFACE_H

#include <simics/base/attr-value.h>  // attr_value_t
#include <simics/base/time.h>  // cycles_t

#include <string>

namespace simics {

// The interface to operate on a AfterCall
class AfterCallInterface {
  public:
    virtual ~AfterCallInterface() = default;
    // Return a unique identifier for the function
    // It consists of the function's name and the typeid string
    virtual std::string name() const = 0;
    // Make a copy of the function call
    virtual AfterCallInterface *make_copy() = 0;
    // Set arguments for the function call
    virtual void set_args(const attr_value_t &args) = 0;
    // Invoke the function with set arguments
    virtual void invoke() = 0;
    // Get the function call information as a Simics attribute
    virtual attr_value_t get_value() = 0;
};

// Interface used to schedule and cancel after calls
class AfterInterface {
  public:
    virtual ~AfterInterface() = default;
    // Schedules a previously registered callback to be executed after
    // a specified delay with provided arguments
    virtual void schedule(double seconds, const std::string &name,
                          const attr_value_t &args) = 0;
    virtual void schedule(cycles_t cycles, const std::string &name,
                          const attr_value_t &args) = 0;
    // Cancels all scheduled callbacks
    virtual void cancel_all() = 0;
};

}  // namespace simics

#endif
