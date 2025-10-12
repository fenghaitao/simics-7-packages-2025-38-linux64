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

#ifndef SIM_PRINT_PRINT_HPP_
#define SIM_PRINT_PRINT_HPP_

#include <iostream>
#include <sstream>

#pragma once

//#define ENABLE_SIM_DEBUG

#ifdef ENABLE_SIM_DEBUG

#define SIM_DEBUG( _stream) \
    { \
        std::cerr << "SME DEBUG: " << _stream << std::endl; \
    }

#define SIM_DEBUG_NO_NEWLINE( _stream) \
    { \
        std::cerr << "SME DEBUG: " << _stream; \
    }

#define SIM_DEBUG_CONCAT( _stream) \
    { \
        std::cerr << " " << _stream; \
    }

#define SIM_DEBUG_END( _stream) \
    { \
        std::cerr << " " << _stream << std::endl; \
    }

#else

#define SIM_DEBUG( _stream)
#define SIM_DEBUG_NO_NEWLINE( _stream)
#define SIM_DEBUG_CONCAT( _stream)
#define SIM_DEBUG_END( _stream)

#endif

#define SIM_LOG_INFO_STREAM( _level, _object, _id, _stream) \
    { \
        std::stringstream ss; \
        ss << _stream; \
        SIM_LOG_INFO( _level, _object, _id, ss.str().c_str()); \
    }

#define SIM_ERROR( _stream) \
    { \
        std::cerr << "SME ERROR: " << _stream << std::endl; \
    }

#endif /* SIM_PRINT_PRINT_HPP_ */
