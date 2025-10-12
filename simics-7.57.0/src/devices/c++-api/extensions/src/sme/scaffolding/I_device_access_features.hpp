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

#ifndef I_BANK_PORT_HPP_
#define I_BANK_PORT_HPP_

#include "sme/scaffolding/features/features.hpp"

namespace sme
{

/**
 * @brief interface for device access features
 *        technically 1 level of indirection which is not necessary in this case.
 *        keeping for consistency.
 * 
 * @tparam T_BANK_PORT is the unique BankPort class
 * @tparam FEATURES is set to one or more access_features (boolean or)
 */
template< typename T_BANK_PORT, uint8_t FEATURES>
class I_device_access_features : public I_DEVICE_ACCESS_FEATURES_APPLY< T_BANK_PORT, FEATURES> {
public:

};

}

#endif
