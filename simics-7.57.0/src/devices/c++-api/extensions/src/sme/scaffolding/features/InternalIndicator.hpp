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

#ifndef CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_INTERNAL_INDICATOR_H
#define CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_INTERNAL_INDICATOR_H

#include "simics/cc-api.h"
#include "simics/cc-modeling-api.h"

#include <vector>

namespace sme
{

struct access_type {
    enum E {
        NO = 0,
        FROM_ATTRIBUTE = 1,
        FROM_internal_METHOD = 2
    };
};

/**
 * @brief Manage internal access to the register, meaning that the register and field access
 *        specializations are bypassed (get/set used instead of read/write).
*/
class InternalIndicator {
public:
    bool is_internal() { return m_internal_access.size() ? m_internal_access.back() > 0 : false; }
    void establish( access_type::E val) { m_internal_access.emplace_back( val); }
    void clear() { m_internal_access.pop_back(); }

private:
    std::vector< access_type::E> m_internal_access;
};

}

#endif
