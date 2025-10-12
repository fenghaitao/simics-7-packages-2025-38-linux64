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

#ifndef CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_FEATURES_H
#define CPP_API_EXTENSIONS_SRC_SME_SCAFFOLDING_FEATURES_FEATURES_H

#include "sme/scaffolding/features/InternalAccessor.hpp"
#include "sme/scaffolding/features/InternalIndicator.hpp"

namespace sme
{

/**
 * @brief feature(s) to enable in scaffolding
 * 
 */
struct access_features {
    enum E {
        NONE            = 0b0000000000000000,
        INTERNAL_ACCESS = 0b0000000000000001,
        CHANGE_ON_READ  = 0b0000000000000010
    };
};

/**
 * @brief Meta Programming definition for access features.  Each feature should have a separate Compiler
 *        Resolved Mnemonic (or ENUM entry)
 */
template< uint8_t FEATURES>
struct ct_features {
    enum {
        has_internal_access = FEATURES & access_features::INTERNAL_ACCESS,
        has_change_on_read  = FEATURES & access_features::CHANGE_ON_READ
    };
};

/**
 * @brief HAS_INTERNAL_INDICATOR is a template meta program to selectively apply the API and storage.
 * 
 * @tparam FEATURES - Logical OR application of one or more features
 * @tparam Enable - using SFINAE, this determines if the Internal Indicator should be applied
 */
template< uint8_t FEATURES, typename Enable = void>
class HAS_INTERNAL_INDICATOR;

template< uint8_t FEATURES>
class HAS_INTERNAL_INDICATOR< FEATURES, typename std::enable_if< !ct_features<FEATURES>::has_internal_access>::type>
{};

template< uint8_t FEATURES>
class HAS_INTERNAL_INDICATOR< FEATURES, typename std::enable_if< ct_features<FEATURES>::has_internal_access>::type>
{ 
public:
    InternalIndicator internal_indicator;
};

/**
 * @brief I_REG_APPLY is a template class which applies one or more template meta programs (decision of application)
 * 
 * @tparam FEATURES - Logical OR application of one or more features
 */
template< uint8_t FEATURES>
class I_REG_APPLY : public HAS_INTERNAL_INDICATOR< FEATURES>
{};

/**
 * @brief HAS_INTERNAL_ACCESSOR is a template meta program to selectively apply the API and storage.
 * 
 * @tparam FEATURES - Logical OR application of one or more features
 * @tparam Enable - using SFINAE, this determines if the Internal Indicator should be applied
 */
template< typename T, uint8_t FEATURES, typename Enable = void>
class HAS_INTERNAL_ACCESSOR;

template< typename T, uint8_t FEATURES>
class HAS_INTERNAL_ACCESSOR< T, FEATURES, typename std::enable_if< !ct_features<FEATURES>::has_internal_access>::type>
{};

template< typename T, uint8_t FEATURES>
class HAS_INTERNAL_ACCESSOR< T, FEATURES, typename std::enable_if< ct_features<FEATURES>::has_internal_access>::type>
: public InternalAccessor<T>
{};

/**
 * @brief I_REG_APPLY is a template class which applies one or more template meta programs (decision of application)
 * 
 * @tparam T_INTERNAL_ACCESSOR - CLASS required tto pass down to HAS_INTERNAL_ACCESSOR
 * @tparam FEATURES - Logical OR application of one or more features
 */
template< typename T_INTERNAL_ACCESSOR, uint8_t FEATURES>
class I_DEVICE_ACCESS_FEATURES_APPLY : public HAS_INTERNAL_ACCESSOR< T_INTERNAL_ACCESSOR, FEATURES>
{};

}

#endif
