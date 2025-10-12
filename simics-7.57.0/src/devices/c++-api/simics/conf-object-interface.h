// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_CONF_OBJECT_INTERFACE_H
#define SIMICS_CONF_OBJECT_INTERFACE_H

namespace simics {

/**
 * Abstract C++ interface contains methods for register model defined
 * behavior after the construction and before the destruction.
 */
class ConfObjectInterface {
  public:
    virtual ~ConfObjectInterface() = default;
    // This method is called in the finalize phase, once the object has been
    // fully constructed.
    virtual void finalize() = 0;
    // This method is called after finalize has been called on all objects
    virtual void objects_finalized() = 0;
};

}  // namespace simics

#endif
