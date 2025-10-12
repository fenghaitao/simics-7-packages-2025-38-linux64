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

#ifndef SIMICS_DETAIL_ATTRIBUTE_EXCEPTIONS_H
#define SIMICS_DETAIL_ATTRIBUTE_EXCEPTIONS_H

#include <exception>
#include <string>

namespace simics {
namespace detail {

class SetInterfaceNotFound : public std::exception {
  public:
    explicit SetInterfaceNotFound(const std::string &msg)
        : msg_(msg) {}

    const char *what() const noexcept override {
        return msg_.c_str();
    }

  private:
    std::string msg_;
};

class SetIllegalType : public std::exception {
  public:
    explicit SetIllegalType(const std::string &msg)
        : msg_(msg) {}

    const char *what() const noexcept override {
        return msg_.c_str();
    }

  private:
    std::string msg_;
};

class SetIllegalValue : public std::exception {
  public:
    explicit SetIllegalValue(const std::string &msg)
        : msg_(msg) {}

    const char *what() const noexcept override {
        return msg_.c_str();
    }

  private:
    std::string msg_;
};

class SetNotWritable : public std::exception {
  public:
    explicit SetNotWritable(const std::string &msg)
        : msg_(msg) {}

    const char *what() const noexcept override {
        return msg_.c_str();
    }

  private:
    std::string msg_;
};

}  // namespace detail
}  // namespace simics

#endif
