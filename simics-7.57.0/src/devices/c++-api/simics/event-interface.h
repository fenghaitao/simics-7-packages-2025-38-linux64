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

#ifndef SIMICS_EVENT_INTERFACE_H
#define SIMICS_EVENT_INTERFACE_H

#include <simics/base/event.h>  // pc_step_t
#include <simics/base/time.h>  // cycles_t

#include <type_traits>  // add_pointer_t

namespace simics {

/**
 * An event is required to implement the interface
 */
class EventInterface {
  public:
    virtual ~EventInterface() = default;
    /// Called when the event expires
    virtual void callback(void *data) = 0;
    /// Called when the event is removed from the queue
    /// without being called
    virtual void destroy(void *data) = 0;
    /// Called to convert the event data into a value
    /// that can be saved in a configuration
    virtual attr_value_t get_value(void *data) = 0;
    /// Called to convert a configuration value into event data
    virtual void *set_value(attr_value_t value) = 0;
    /// Called to generate a human-readable description of the
    /// event to be used in the print-event-queue command
    virtual char *describe(void *data) const = 0;
};

class TimeEventInterface {
  public:
    virtual ~TimeEventInterface() = default;
    /// Removes all events of this type with matching data from the queue
    virtual void remove(void *match_data) const = 0;
    /// Returns true if the event is in the queue, and false otherwise.
    virtual bool posted(void *match_data) const = 0;
    /// Returns the time to the next occurrence of the event in the queue
    /// (relative to the current time)
    virtual double next(void *data) const = 0;
    /// Posts the event on the associated queue of the device
    virtual void post(double seconds, void *data) = 0;
};

class CycleEventInterface {
  public:
    virtual ~CycleEventInterface() = default;
    /// Removes all events of this type with matching data from the queue
    virtual void remove(void *match_data) const = 0;
    /// Returns true if the event is in the queue, and false otherwise.
    virtual bool posted(void *match_data) const = 0;
    /// Returns the cycles to the next occurrence of the event in the queue
    /// (relative to the current time)
    virtual cycles_t next(void *match_data) const = 0;
    /// Posts the event on the associated queue of the device
    virtual void post(cycles_t cycles, void *data) = 0;
};

class StepEventInterface {
  public:
    virtual ~StepEventInterface() = default;
    /// Removes all events of this type with matching data from the queue
    virtual void remove(void *match_data) const = 0;
    /// Returns true if the event is in the queue, and false otherwise.
    virtual bool posted(void *match_data) const = 0;
    /// Returns the steps to the next occurrence of the event in the queue
    /// (relative to the current time)
    virtual pc_step_t next(void *match_data) const = 0;
    /// Posts the event on the associated queue of the device
    virtual void post(pc_step_t steps, void *data) = 0;
};

}  // namespace simics

#endif
