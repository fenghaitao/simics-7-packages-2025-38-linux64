// -*- mode: C++; c-file-style: "virtutech-c++" -*-

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

#ifndef UNITTEST_MOCK_COUNTED_INT_H
#define UNITTEST_MOCK_COUNTED_INT_H

#include <simics/attribute-traits.h>

#include <iostream>

class CountedInt {
  public:
    explicit CountedInt(int val = 0) : value(val) {}

    // Copy constructor
    CountedInt(const CountedInt &other) : value(other.value) {
        ++copyConstructorCalls;
        std::cout << "Copy constructor called. Total calls: "
                  << copyConstructorCalls << std::endl;
    }

    // Copy assignment operator
    CountedInt& operator=(const CountedInt &other) {
        if (this != &other) {
            value = other.value;
            ++copyAssignmentCalls;
            std::cout << "Copy assignment called. Total calls: "
                      << copyAssignmentCalls << std::endl;
        }
        return *this;
    }

    // Getter for the value
    int getValue() const { return value; }

    // Static methods to get the counts
    static int getCopyConstructorCalls() { return copyConstructorCalls; }
    static int getCopyAssignmentCalls() { return copyAssignmentCalls; }

    // Reset counters (for testing purposes)
    static void resetCounters() {
        copyConstructorCalls = 0;
        copyAssignmentCalls = 0;
    }

  private:
    int value;
    static inline int copyConstructorCalls {0};
    static inline int copyAssignmentCalls {0};
};

template <>
struct simics::detail::attr_from_std_helper<CountedInt> {
    static attr_value_t f(const CountedInt &src) {
        return SIM_make_attr_int64(src.getValue());
    }
};

#endif
