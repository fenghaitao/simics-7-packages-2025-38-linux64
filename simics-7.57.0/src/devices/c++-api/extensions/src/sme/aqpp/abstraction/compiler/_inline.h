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

#ifndef CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER__INLINE_H
#define CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER__INLINE_H

#include "sme/aqpp/abstraction/compiler/identification.h"

// This library does not rely on intrinsic inlign-ing of the compiler

#if defined( SUPPORT_GCC_ATTRIBUTES)
    #define _always_inline __attribute__((always_inline)) inline
    #define _fast_func __attribute__((always_inline, flatten, hot)) inline
    #define _keep_hot __attribute__((flatten, hot))
#elif defined( SUPPORT_MS_ATTRIBUTES)
    #define _always_inline __forceinline
    #define _fast_func __forceinline
    #define _keep_hot
#else
    #define _always_inline inline
    #define _fast_func inline
    #define _keep_hot
#endif


#endif /* ABSTRACTION_COMPILER__INLINE_H_ */
