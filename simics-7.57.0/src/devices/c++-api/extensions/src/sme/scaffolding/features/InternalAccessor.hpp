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

//-*- C++ -*-

#ifndef CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_INTERNAL_ACCESSOR_H
#define CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_INTERNAL_ACCESSOR_H

#include "simics/cc-api.h"
#include "simics/cc-modeling-api.h"

namespace sme
{

/**
 * @brief pass through wrapper; adds internal_access attribute and customized getters/setters
 *
 * @tparam T is a definition of BankPort
 */
template<typename T>
class InternalAccessor {
public:
    static void init_class(simics::ConfClass* cls) {
        cls->add(simics::Attribute("internal_access", "b",
                                   "set to cause next transaction to bypass register specializations",
                                   &get_internal_trampoline, &set_internal_trampoline, Sim_Attr_Pseudo));
    }

public:
    static attr_value_t get_internal_trampoline(conf_object* obj) {
        auto ptr = simics::from_obj<T>(obj);
        return SIM_make_attr_boolean(ptr->get_one_shot());
    }

    static set_error_t set_internal_trampoline(conf_object_t* obj, attr_value_t* attr) {
        auto ptr = simics::from_obj<T>(obj);
        ptr->set_internal(SIM_attr_boolean(*attr));
        return Sim_Set_Ok;
    }

    void set_internal(bool val) { internal = val; }

    bool get_one_shot() {
        auto val = internal;
        internal = false;
        return val;
    }

    bool internal = false;
};

}

#endif
