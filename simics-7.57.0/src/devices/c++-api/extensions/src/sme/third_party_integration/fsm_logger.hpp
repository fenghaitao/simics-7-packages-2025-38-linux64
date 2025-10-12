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

#ifndef FSM_LOGGER_HPP
#define FSM_LOGGER_HPP

#include "sme/sme.h"
namespace sml = boost::sml;

namespace extras {

struct fsm_logger {
    template <class SM, class TEvent>
    void log_process_event(const TEvent&) {
        printf("[%-20s][process_event] %s\n", sml::aux::get_type_name<SM>(), sml::aux::get_type_name<TEvent>());
    }

    template <class SM, class TGuard, class TEvent>
    void log_guard(const TGuard&, const TEvent&, bool result) {
        printf("[%-20s][guard        ] %s %s %s\n", sml::aux::get_type_name<SM>(), sml::aux::get_type_name<TGuard>(),
            sml::aux::get_type_name<TEvent>(), (result ? "[OK]" : "[Reject]"));
    }

    template <class SM, class TAction, class TEvent>
    void log_action(const TAction&, const TEvent&) {
        printf("[%-20s][action       ] %s %s\n", sml::aux::get_type_name<SM>(), sml::aux::get_type_name<TAction>(),
            sml::aux::get_type_name<TEvent>());
    }

    template <class SM, class TSrcState, class TDstState>
    void log_state_change(const TSrcState& src, const TDstState& dst) {
        printf("[%-20s][transition   ] %s -> %s\n", sml::aux::get_type_name<SM>(), src.c_str(), dst.c_str());
    }
};

}

#endif