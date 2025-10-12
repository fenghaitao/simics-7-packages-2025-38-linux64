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

#ifndef SIMICS_OBJECT_FACTORY_H
#define SIMICS_OBJECT_FACTORY_H

#include <type_traits>  // is_base_of

#include "simics/object-factory-interface.h"
#include "simics/conf-object.h"

namespace simics {

/**
 * @brief A factory for creating instances of ConfObject-derived classes.
 *
 * The ObjectFactory class template provides a factory for creating instances
 * of classes derived from ConfObject. It implements the ObjectFactoryInterface.
 *
 * @tparam T The type of the ConfObject-derived class to be created.
 */
template <typename T>
class ObjectFactory : public ObjectFactoryInterface {
  public:
    static_assert(std::is_base_of<ConfObject, T>::value,
                  "T must be ConfObject-derived");

    ObjectFactory() = default;

    /**
     * @brief Creates an instance of the ConfObject-derived class.
     *
     * This function creates and returns a new instance of the ConfObject-derived
     * class using the provided conf_object_t pointer.
     *
     * @param obj Pointer to a conf_object_t instance.
     * @return Pointer to a newly created ConfObject-derived instance.
     */
    ConfObject *create(conf_object_t *obj) const override {
        return new T(obj);
    }

    /**
     * @brief Clones the current ObjectFactory instance.
     *
     * This function creates and returns a copy of the current ObjectFactory instance.
     *
     * @return Pointer to a cloned ObjectFactory instance.
     */
    ObjectFactoryInterface *clone() const override {
        return new ObjectFactory<T>();
    }
};

/**
 * @brief A factory for creating instances of ConfObject-derived classes with an argument.
 *
 * The ObjectFactoryWithArg class template provides a factory for creating instances
 * of classes derived from ConfObject, with an additional argument passed to the constructor.
 * It implements the ObjectFactoryInterface.
 *
 * @tparam T The type of the ConfObject-derived class to be created.
 * @tparam A The type of the additional argument to be passed to the constructor.
 */
template <typename T, typename A>
class ObjectFactoryWithArg : public ObjectFactoryInterface {
  public:
    static_assert(std::is_base_of<ConfObject, T>::value,
                  "T must be ConfObject-derived");

    explicit ObjectFactoryWithArg(A *arg): arg_(arg) {}

    /**
     * @brief Creates an instance of the ConfObject-derived class with an argument.
     *
     * This function creates and returns a new instance of the ConfObject-derived
     * class using the provided conf_object_t pointer and the additional argument.
     *
     * @param obj Pointer to a conf_object_t instance.
     * @return Pointer to a newly created ConfObject-derived instance.
     */
    ConfObject *create(conf_object_t *obj) const override {
        return new T(obj, arg_);
    }

    /**
     * @brief Clones the current ObjectFactoryWithArg instance.
     *
     * This function creates and returns a copy of the current ObjectFactoryWithArg instance.
     *
     * @return Pointer to a cloned ObjectFactoryWithArg instance.
     */
    ObjectFactoryInterface *clone() const override {
        return new ObjectFactoryWithArg(arg_);
    }

  private:
    A *arg_;
};

}  // namespace simics

#endif
