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

#ifndef I_REGISTER_HPP_
#define I_REGISTER_HPP_

#include "sme/overlays/callback_overlay.h"
#include "sme/scaffolding/features/features.hpp"
#include <vector>

namespace sme
{

class I_field;

/**
 * @brief method interface for sme::register.
 * 
 */
template< uint8_t FEATURES>
class I_reg : public callback_overlay, public I_REG_APPLY< FEATURES> {
public:

    /**
     * @brief Get if the developer has implemented the object.
     * 
     * @return true 
     * @return false 
     */
    virtual bool get_implemented() = 0;

    /**
     * @brief Set if the developer had implemented the object.
     * 
     */
    virtual void set_implemented() = 0;

    /**
     * @brief returns if the transaction is initiated from a register or not (field).
     * 
     * @return true 
     * @return false 
     */
    virtual bool is_register_transaction() = 0;

    /**
     * @brief set the transaction to indicate if it is initiated from a register or not (field).
     *
     */
    virtual void set_register_transaction(bool value) = 0;

    /**
     * @brief api pass through: name() - returns name of register.
     * 
     * @return std::string_view
     */
    virtual std::string_view __name() = 0;

    /**
     * @brief api pass through: get() - returns value of register.
     * 
     * @return uint64_t 
     */
    virtual uint64_t __get() = 0;

};

}

#endif
