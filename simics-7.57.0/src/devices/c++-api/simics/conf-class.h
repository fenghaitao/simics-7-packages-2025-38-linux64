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

#ifndef SIMICS_CONF_CLASS_H
#define SIMICS_CONF_CLASS_H

#include <simics/base/conf-object.h>  // class_kind_t

#include <map>
#include <memory>  // unique_ptr
#include <string>
#include <vector>

#include "simics/attribute.h"
#include "simics/event.h"
#include "simics/init-class.h"
#include "simics/iface/interface-info.h"
#if defined INTC_EXT
#include "simics/iface/object-factory-interface.h"
#endif
#include "simics/log.h"  // LogGroups
#include "simics/object-factory.h"

namespace simics {

using ConfClassPtr = std::unique_ptr<ConfClass>;

/**
 * Represents Simics C type conf_class_t.
 *
 * This class serves as a wrapper around a `conf_class_t` pointer, providing
 * comprehensive support for the registration of attributes, interfaces, log
 * groups, and ports.
 *
 * Instances of this class cannot be created using a default constructor, as
 * a valid `conf_class_t` pointer is required for initialization. To ensure
 * proper setup and validation, the class employs a static factory function,
 * `createInstance`, as the sole method for instantiation. 
 */
class ConfClass {
  public:
    /**
     * Factory function to create a ConfClass instance
     * All parameters except the last one is used to call the Simics
     * C API SIM_create_class. May raise runtime_error if the creation
     * failed.
     *
     * @see SIM_create_class
     * @param factory an interface to create ConfObject.
     * @return a ConfClassPtr
     */
    static ConfClassPtr createInstance(
            const std::string &name,
            const std::string &short_desc,
            const std::string &description,
            const class_kind_t kind,
            const ObjectFactoryInterface &factory);

#if defined INTC_EXT
    /// to maintain ABI compatibility with Simics Base version 6.0.215
    static ConfClassPtr createInstance(
            const std::string &name,
            const std::string &short_desc,
            const std::string &description,
            const class_kind_t kind,
            const iface::ObjectFactoryInterface &factory);
#endif

    /// Avoid implicit copy
    ConfClass(const ConfClass&) = delete;
    ConfClass& operator=(const ConfClass&) = delete;

    virtual ~ConfClass();

    /**
     * Return the ID of a log group
     */
    static uint64 getGroupId(conf_class_t *cls, const std::string &name);

    /**
     * Get a pointer to the configuration class represented
     */
    operator conf_class_t*() const;

    /**
     * Return the class name
     */
    const std::string &name() const;

    /**
     * Return the class description
     */
    const std::string &description() const;

    /**
     * Return the class log groups
     */
    const std::vector<std::string> &log_groups() const;

    /**
     * Stores the provided InterfaceInfo for later registration.
     * The actual registration with SIM_register_interface will be performed
     * when the ConfClass object is destroyed.
     *
     * @see SIM_register_interface
     * @param iface a Registry used for interface registration.
     * @return ConfClass this pointer
     */
    ConfClass *add(const iface::InterfaceInfo &iface);

    /**
     * A function to add an attribute to the set of attributes of ConfClass.
     *
     * @see SIM_register_attribute, SIM_register_class_attribute
     * @param attr an Attribute used for adding an attribute.
     * @return ConfClass this pointer
     */
    ConfClass *add(const Attribute &attr);
    ConfClass *add(const ClassAttribute &attr);

    /**
     * Functions to add log groups that an object can use to separate messages.
     * A class may have up to 63 user-defined log groups.
     * The Simics log groups can be registered either by calling these
     * functions one or more times, or by calling the
     * SIM_log_register_groups C API function directly. It is not permitted to
     * use both of them in one ConfClass.
     *
     * @param names either a NULL-terminated array or a list of strings
                    contains names of the log groups
     * @return ConfClass this pointer
     */
    ConfClass *add(const char * const *names);
    ConfClass *add(const LogGroups &names);

    /**
     * A function to add a port object to the set of ports defined by the class.
     *
     * @see SIM_register_port
     * @param port a ConfClass to be used as port object
     * @param name the name of the port object
     * @return ConfClass this pointer
     *
     * If the name contains a pair of brackets, for instance, "port.array[2]"
     * registers a port array with two ports "port.array[0]" and "port.array[1]"
     * Multidimensional array format is not supported
     */
    ConfClass *add(ConfClass *port, const std::string &name);
    ConfClass *add(const ConfClassPtr &port, const std::string &name);

    /**
     * A function to add an event to the set of events of ConfClass.
     *
     * @see SIM_register_event
     * @param event the event to be registered on the class
     * @return ConfClass this pointer
     */
    ConfClass *add(EventInfo &&event);

  protected:
    /// Must use factory method to create instance
    explicit ConfClass(conf_class_t *cls, const std::string &name,
                       const std::string &description)
        : cls_(cls), name_(name), description_(description) {}

  private:
    /// Internal. Register log_groups_ as Simics log groups to cls_.
    void register_log_groups() const noexcept;

    /// Internal. Register pending_interfaces_ as Simics interfaces to cls_.
    void register_interfaces() noexcept;

    conf_class_t *cls_ {nullptr};
    std::string name_;
    std::string description_;
    std::vector<std::string> log_groups_;
    std::map<std::string, const interface_t *> pending_interfaces_;
};

/// Overload it with specific implementation by including the other
/// header before this file
template <typename T>
void decorate_class(...) {}

/**
 * A factory method to create a ConfClassPtr which associate with
 * the C++ class T. It calls init_class if T defines it.
 *
 * @see ConfClass#create
 * @param name the name of the creating class.
 * @param short_desc a short class description for the class.
 * @param description a description string describes the class.
 * @param kind an enum determine if the configuration object should be saved
 *             when a checkpoint is created.
 * @return a ConfClassPtr
 */
template <typename T> ConfClassPtr
make_class(const std::string &name, const std::string &short_desc,
           const std::string &description,
           const class_kind_t kind = Sim_Class_Kind_Vanilla) {
    auto cls = ConfClass::createInstance(name, short_desc, description, kind,
                                         ObjectFactory<T>());
    detail::init_class<T>(cls.get());
    decorate_class<T>(nullptr, cls.get());
    return cls;
}

/**
 * A factory method to create a ConfClassPtr which associate with
 * the C++ class T with argument A. It calls init_class if T defines it.
 *
 * @see ConfClass#create
 * @param name the name of the creating class.
 * @param short_desc a short class description for the class.
 * @param description a description string describes the class.
 * @param constructor_arg argument passed to the object factory constructor.
 * @param kind an enum determine if the configuration object should be saved
 *             when a checkpoint is created.
 * @return a ConfClassPtr
 */
template <typename T, typename A> ConfClassPtr
make_class(const std::string &name, const std::string &short_desc,
           const std::string &description, A *constructor_arg,
           const class_kind_t kind = Sim_Class_Kind_Vanilla) {
    auto cls = ConfClass::createInstance(name, short_desc, description, kind,
                                         ObjectFactoryWithArg<T, A>(
                                                 constructor_arg));
    detail::init_class<T>(cls.get());
    decorate_class<T>(nullptr, cls.get());
    return cls;
}

// Custom empty class used as a placeholder for "no additional argument"
class None {};

/**
 * @brief Utility class for automatic registration of C++ classes with Simics.
 *
 * This class template provides a convenient way to register C++ classes with
 * the Simics simulation framework. It automatically calls the appropriate
 * `make_class` function during static initialization, ensuring that the class
 * is properly registered when the module is loaded.
 *
 * @tparam T The C++ class to be registered with Simics.
 * @tparam A (optional) Additional argument type for the class constructor.
 *
 * Usage example:
 * @code
 * static RegisterClassWithSimics<MyClass> register_my_class(
 *     "my_class", "Short description", "Detailed description");
 * @endcode
 *
 * @note Using a static global instance of this class may trigger a Coverity
 *       warning such as `global_init_order` or `ctor_dtor_global_ordering`
 *       due to potential global initialization order issues. As there are no
 *       dependencies on the initialization order for registration object,
 *       you can safely suppress this warning by adding the following comment
 *       immediately before the static variable:
 *       // coverity[ctor_dtor_global_ordering]
 */
template <typename T, typename A = None>
class RegisterClassWithSimics {
    // This type is defined (as int) only when A is None
    template <typename U = A>
    using EnableIfNone = std::enable_if_t<std::is_same<U, None>::value, int>;

    // This type is defined (as int) only when A is not None
    template <typename U = A>
    using EnableIfNotNone = std::enable_if_t<!std::is_same<U, None>::value,
                                             int>;

  public:
    // Constructor for classes without additional arguments
    template <typename U = A, EnableIfNone<U> = 0> constexpr
    RegisterClassWithSimics(const std::string &name,
                            const std::string &short_desc,
                            const std::string &description,
                            const class_kind_t kind = Sim_Class_Kind_Vanilla) {
        make_class<T>(name, short_desc, description, kind);
    }

    // Constructor for classes with additional arguments
    template <typename U = A, EnableIfNotNone<U> = 0> constexpr
    RegisterClassWithSimics(const std::string &name,
                            const std::string &short_desc,
                            const std::string &description,
                            A *constructor_arg,
                            const class_kind_t kind = Sim_Class_Kind_Vanilla) {
        make_class<T, A>(name, short_desc, description, constructor_arg, kind);
    }
};

#define GROUP_ID(...) \
    IMPL(GET_MACRO(__VA_ARGS__, GROUP_ID_TWO_ARGS, \
                   GROUP_ID_ONE_ARG)(__VA_ARGS__))

#define GROUP_ID_ONE_ARG(NAME) \
    simics::ConfClass::getGroupId(SIM_object_class(obj()), #NAME)

#define GROUP_ID_TWO_ARGS(OBJ, NAME) \
    simics::ConfClass::getGroupId(SIM_object_class(OBJ), #NAME)

}  // namespace simics

#endif
