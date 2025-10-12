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

#ifndef SSA_DEVICE_ACCESS_FEATURES_HPP_
#define SSA_DEVICE_ACCESS_FEATURES_HPP_

#include "sme/scaffolding/features/features.hpp"
#include "sme/scaffolding/I_device_access_features.hpp"
#include "sme/aqpp/print/sme_print.hpp"

namespace sme
{

/**
 * @brief pass through wrapper
 *
 * @tparam T_BANK_PORT is the unique BankPort class
 * @tparam FEATURES is set to one or more access_features (boolean or)
 */
template< typename T_BANK_PORT, uint8_t FEATURES = access_features::NONE >
class device_access_features : public I_device_access_features< T_BANK_PORT, FEATURES> {

};

}

#endif
