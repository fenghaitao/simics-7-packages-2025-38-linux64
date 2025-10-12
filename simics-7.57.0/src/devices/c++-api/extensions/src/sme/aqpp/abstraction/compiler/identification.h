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

// -*- C++ -*-

#ifndef CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER_IDENTIFICATION_H
#define CPP_API_EXTENSIONS_SRC_SME_AQPP_ABSTRACTION_COMPILER_IDENTIFICATION_H

// Verify C++ Language Version
#if defined(_MSVC_LANG)
    static_assert(_MSVC_LANG >= 201703L);
#elif defined(__cplusplus)
    // NOTE: even if MSVC_LANG is 201703 or higher, __cplusplus is 1997.. bug in microsoft.
    static_assert( __cplusplus >= 201703L, "C++ 17 is required to use this library");
#endif

// Verify Valid Compiler
#if !(defined( __INTEL_LLVM_COMPILER) || defined( __GNUC__) || defined ( _MSC_VER))
    static_assert( false, "Only GCC, Visual Studio or Intel ICX & DPCPP Compilers Supported at this time.")
#endif

// Verify Minimal Compiler Version(s)
#if defined( SYCL_LANGUAGE_VERSION )
    static_assert( SYCL_LANGUAGE_VERSION >= 202001, "Version 202001 or higher required if using SYCL language.");
#endif

#if defined( __INTEL_LLVM_COMPILER )
    static_assert( __INTEL_LLVM_COMPILER >= 202110, "Version 202110 or higher required if using DPCPP or ICX.");
#endif

#if defined( __GNUC__ )
    static_assert( __GNUC__ >= 11, "Version 11 or higher required if using GNU/GCC.");
#endif

#if defined( _MSC_VER)
    static_assert( _MSC_VER >= 1929, "Version 19.11 or higher required if using Visual Studio.");
#endif

#if defined( __INTEL_LLVM_COMPILER ) || defined( __INTEL_COMPILER ) || defined( __GNUC__ )
    #define SUPPORT_GCC_ATTRIBUTES 1
    #define STANDARD_CPP
#elif defined(WIN32) || defined(_WIN32)
    #define SUPPORT_MS_ATTRIBUTES 1
    #define MSFT_CPP
#endif

#if defined( _MSVC_LANG)
    #if( _MSVC_LANG >= 202002)
        #define CPP20
    #elif (_MSVC_LANG >= 201703L)
        #define CPP17
    #endif
#elif defined( __cplusplus)
    #if (__cplusplus >= 202002L)
        #define CPP20
    #elif (__cplusplus >= 201703L)
        #define CPP17
    #endif
#endif

#if __has_include("windows.h")
    #define ON_WINDOWS
#endif

#endif /* ABSTRACTION_COMPILER__IDENTIFICATION_H_ */

