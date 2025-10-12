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

//-*- C++ -*-

#ifndef CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_I_BANK_ELEMENT_H
#define CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_I_BANK_ELEMENT_H

#include <stdarg.h>
#include <iostream>

#include "sme/aqpp/abstraction/compiler/_inline.h"
#include "sme/overlays/I_callback_overlay.hpp"

namespace sme
{

class I_bank_element  : public I_callback_overlay
{
public:
    
    /**
     * @brief internal_read data from mask
     *
     * @param enabled_bits represents mask
     * @return uint64_t
     */
    virtual uint64_t internal_read(uint64_t enabled_bits = -1ULL) = 0;

    /**
     * @brief internal_write value with mask
     *
     * @param value to write
     * @param enabled_bits represents mask
     */
    virtual void internal_write(uint64_t value, uint64_t enabled_bits = -1ULL) = 0;
};

}

#endif
