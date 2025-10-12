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

#ifndef CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER__PACK_H
#define CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER__PACK_H

#include "sme/aqpp/abstraction/compiler/identification.h"

// Packing is a slightly complex topic, it actually depends greatly on the compiler and harware target
// Many reading material links are supplied as references
// The macros provided are to be utilized for single byte packing only
// Alignment should be addressed with updated standard for C++ using "alignas" and "alignof"

//https://developer.arm.com/documentation/100748/0616/Writing-Optimized-Code/Packing-data-structures

#if defined( SUPPORT_GCC_ATTRIBUTES)
// https://gcc.gnu.org/onlinedocs/gcc-3.3/gcc/Type-Attributes.html
// https://web.mit.edu/rhel-doc/3/rhel-gcc-en-3/variable-attributes.html
// https://debrouxl.github.io/gcc4ti/gnuexts.html
    #define _prepack
    #define _endpack __attribute__((packed))

#elif defined( SUPPORT_MS_ATTRIBUTES)
// https://docs.microsoft.com/en-us/cpp/preprocessor/pack?view=msvc-170
// https://docs.microsoft.com/en-us/cpp/build_target/x64-software-conventions?view=msvc-170#examples-of-structure-alignment
    #define _prepack __pragma( pack( push, 1) )
    #define _endpack __pragma( pack( pop) )

#else // default for unkown compiler
    #define _prepack
    #define _endpack

#endif

#define _pack( __DECL__ ) _prepack __DECL__ _endpack

//https://stackoverflow.com/questions/17091382/memory-alignment-how-to-use-alignof-alignas
//https://developer.ibm.com/articles/pa-dalign//

#endif /* ABSTRACTION_COMPILER__PACK_H_ */
