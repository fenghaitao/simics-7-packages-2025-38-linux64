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

#ifndef SIMICS_OBJECT_FACTORY_INTERFACE_H
#define SIMICS_OBJECT_FACTORY_INTERFACE_H

#include <simics/base/types.h>  // conf_object_t

namespace simics {

class ConfObject;

/**
 * @brief Interface for a factory pattern to create ConfObject instances.
 *
 * The ObjectFactoryInterface defines an interface for creating instances of
 * ConfObject.
 */
class ObjectFactoryInterface {
  public:
    virtual ~ObjectFactoryInterface() = default;

    /**
     * @brief Creates a ConfObject instance from a conf_object_t pointer.
     *
     * This function creates and returns a pointer to a ConfObject instance
     * using the provided conf_object_t pointer.
     *
     * @param obj Pointer to a conf_object_t instance.
     * @return Pointer to a newly created ConfObject instance.
     */
    virtual ConfObject *create(conf_object_t *obj) const = 0;

    /**
     * @brief Clones the current ObjectFactoryInterface instance.
     *
     * This function creates and returns a copy of the current
     * ObjectFactoryInterface instance.
     *
     * @return Pointer to a cloned ObjectFactoryInterface instance.
     */
    virtual ObjectFactoryInterface *clone() const = 0;
};

}  // namespace simics

#endif
