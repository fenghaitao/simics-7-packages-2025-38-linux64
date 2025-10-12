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

#ifndef SIMICS_EVENT_H
#define SIMICS_EVENT_H

#include <simics/base/event.h>  // event_class_flag_t
#include <simics/base/sim-exception.h>  // SIM_clear_exception
#include <simics/base/time.h>  // SIM_object_clock

#include <stdexcept>
#include <string>
#include <type_traits>  // add_pointer_t

#include "simics/conf-object.h"
#include "simics/detail/event-helper.h"
#include "simics/event-interface.h"
#include "simics/log.h"

namespace simics {

using ev_callback = std::add_pointer_t<void(conf_object_t *, void *)>;
using ev_destroy = ev_callback;
using ev_value_getter = std::add_pointer_t<attr_value_t(conf_object_t *obj,
                                                        void *data)>;
using ev_value_setter = std::add_pointer_t<void *(conf_object_t *obj,
                                                       attr_value_t value)>;
using ev_describe = std::add_pointer_t<char *(conf_object_t *obj,
                                              void *data)>;

/*
 * Class provides information for event registration
 * @see ConfClass *add(EventInfo &&event)
 */
struct EventInfo {
    EventInfo(const std::string &name, event_class_flag_t flags,
              event_class_t **ev, ev_callback callback, ev_destroy destroy,
              ev_value_getter get_value, ev_value_setter set_value,
              ev_describe describe);
    EventInfo(const std::string &name, event_class_t **ev,
              ev_callback callback);

    std::string name;
    event_class_flag_t flags;
    event_class_t **ev {nullptr};
    ev_callback callback;
    ev_destroy destroy;
    ev_value_getter get_value;
    ev_value_setter set_value;
    ev_describe describe;
};

/**
 * The Event class allows users to define callbacks that will be executed after
 * a specified delay.
 *
 * The delay can be measured in different units depending on the type of event
 * being created.
 *
 * Users should inherit from one of the Simics provided classes based on their
 * desired timebase:
 *
 * - simics::TimeEvent: Used when the delay is measured in seconds
 * - simics::CycleEvent: Used when the delay is measured by the number of cycles
 * - simics::StepEvent: Used when the delay is measured by the number of steps
 */
class Event : public EventInterface {
  public:
    /// @param obj should be an instance of the same class the event is
    ///            registered on
    /// @param ev should be pointed to the registered Simics event class
    ///            (e.g., SIM_register_event)
    Event(ConfObject *obj, event_class_t *ev);
    /// @param name is the name of the event class registered
    Event(ConfObject *obj, const std::string &name);

    // EventInterface
    void destroy(void *data) override;
    attr_value_t get_value(void *data) override;
    void *set_value(attr_value_t value) override;
    char *describe(void *data) const override;

    operator event_class_t *() const;

  protected:
    static int pointer_eq(void *data, void *match_data);

    /// @return pointer of the device class instance contains
    ///         this event instance
    template <typename T> T *device_ptr() const {
        static_assert(std::is_base_of<ConfObject, T>::value,
                      "T must be a descendant of ConfObject");
        return static_cast<T *>(obj_);
    }

    const char *name() const;

    ConfObject *obj_ {nullptr};
    event_class_t *ev_ {nullptr};
    /// clock_ cannot be initialized here by SIM_object_clock,
    /// since attribute queue is not set yet
    conf_object_t *clock_ {nullptr};
};

/// Time-based event type
template <typename T = ConfObject>
class TimeEvent : public Event,
                  public TimeEventInterface {
  public:
    using Event::Event;

    // TimeEventInterface
    bool posted(void *match_data = nullptr) const override {
        return next(match_data) >= 0.0;
    }

    void remove(void *match_data = nullptr) const override {
        if (clock_) {
            SIM_event_cancel_time(clock_, ev_, obj_->obj(),
                                  Event::pointer_eq, match_data);
        }
    }

    void post(double seconds, void *data = nullptr) override {
        if (clock_ == nullptr) {
            /// clock_ is initialized when event is posted
            clock_ = SIM_object_clock(obj_->obj());
            if (clock_ == nullptr) {
                SIM_LOG_ERROR(obj_->obj(), 0,
                              "Queue not set, unable to post events");
                return;
            }
        }
        SIM_event_post_time(clock_, ev_, obj_->obj(), seconds, data);
        if (SIM_clear_exception() != SimExc_No_Exception) {
            SIM_LOG_ERROR(obj_->obj(), 0, "%s", SIM_last_error());
        }
    }

    double next(void *match_data = nullptr) const override {
        if (clock_ == nullptr) {
            return -1.0;
        }
        return SIM_event_find_next_time(clock_, ev_, obj_->obj(),
                                        Event::pointer_eq, match_data);
    }

  protected:
    T *dev_ {device_ptr<T>()};
};

/// Cycle-based event type
template <typename T = ConfObject>
class CycleEvent : public Event,
                   public CycleEventInterface {
  public:
    using Event::Event;

    // CycleEventInterface
    bool posted(void *match_data = nullptr) const override {
        return next(match_data) >= 0;
    }

    void remove(void *match_data = nullptr) const override {
        if (clock_) {
            // There is no SIM_event_cancel_cycle
            SIM_event_cancel_time(clock_, ev_, obj_->obj(),
                                  Event::pointer_eq, match_data);
        }
    }

    void post(cycles_t cycles, void *data = nullptr) override {
        if (clock_ == nullptr) {
            /// clock_ is initialized when event is posted
            clock_ = SIM_object_clock(obj_->obj());
        }
        SIM_event_post_cycle(clock_, ev_, obj_->obj(), cycles, data);
        if (SIM_clear_exception() != SimExc_No_Exception) {
            SIM_LOG_ERROR(obj_->obj(), 0, "%s", SIM_last_error());
        }
    }

    cycles_t next(void *match_data = nullptr) const override {
        if (clock_ == nullptr) {
            return -1;
        }
        return SIM_event_find_next_cycle(clock_, ev_, obj_->obj(),
                                         Event::pointer_eq, match_data);
    }

  protected:
    T *dev_ {device_ptr<T>()};
};

/// Not commonly used for device model. Step-based event type
template <typename T = ConfObject>
class StepEvent : public Event,
                  public StepEventInterface {
  public:
    using Event::Event;

    // StepEventInterface
    bool posted(void *match_data = nullptr) const override {
        return next(match_data) >= 0;
    }

    void remove(void *match_data = nullptr) const override {
        if (clock_) {
            SIM_event_cancel_step(clock_, ev_, obj_->obj(),
                                  Event::pointer_eq, match_data);
        }
    }

    void post(pc_step_t steps, void *data = nullptr) override {
        if (clock_ == nullptr) {
            /// clock_ is initialized when event is posted
            clock_ = SIM_object_clock(obj_->obj());
        }
        SIM_event_post_step(clock_, ev_, obj_->obj(), steps, data);
        if (SIM_clear_exception() != SimExc_No_Exception) {
            SIM_LOG_ERROR(obj_->obj(), 0, "%s", SIM_last_error());
        }
    }

    pc_step_t next(void *match_data = nullptr) const override {
        if (clock_ == nullptr) {
            return -1;
        }
        return SIM_event_find_next_step(clock_, ev_, obj_->obj(),
                                        Event::pointer_eq, match_data);
    }

  protected:
    T *dev_ {device_ptr<T>()};
};

}  // namespace simics

#endif
