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

#ifndef CPP_API_EXTENSIONS_SRC_SME_SME_H
#define CPP_API_EXTENSIONS_SRC_SME_SME_H

#include <simics/cc-modeling-api.h>

#include "sml-1.1.9/include/boost/sml.hpp"

#include "sme/aqpp/abstraction/compiler/identification.h"
#include "sme/aqpp/print/sme_print.hpp"
#include "sme/aqpp/foundation/callables/action.hpp"

#include "sme/expressions/expression.hpp"

#include "sme/overlays/callback_overlay.h"
#include "sme/overlays/bank_element.hpp"

#include "sme/pattern_rules/falling_bit.h"
#include "sme/pattern_rules/rising_bit.h"
#include "sme/pattern_rules/masked.h"
#include "sme/pattern_rules/notify.h"
#include "sme/pattern_rules/pattern.h"
#include "sme/pattern_rules/falling.h"
#include "sme/pattern_rules/rising.h"
#include "sme/pattern_rules/user_defined.h"

#include "sme/scaffolding/ssa_field.hpp"
#include "sme/scaffolding/ssa_register.hpp"
#include "sme/scaffolding/ssa_device_access_features.hpp"

#include "sme/third_party_integration/fsm_logger.hpp"

#endif

