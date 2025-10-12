/*
  © 2010 Intel Corporation
*/

// empty-device-cc.cc - Skeleton code to base new C++ device modules on

#include <simics/cc-api.h>
#include <simics/c++/model-iface/transaction.h>

#include <iostream>

class empty_device_cc_instance : public simics::ConfObject,
                                 public simics::iface::TransactionInterface {
  public:
    explicit empty_device_cc_instance(simics::ConfObjectRef o)
        : simics::ConfObject(o),
          value(0) {};

    // USER-TODO: Add user specific members here. The 'value' member is only an
    // example to show how to implement an attribute
    int value;

    // USER-TODO: Add implemented ports and interfaces here
    exception_type_t issue(transaction_t *t, uint64 addr) override;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::iface::TransactionInterface::Info());
        cls->add(simics::Attribute(
                         "value", "i", "A value.",
                         ATTR_CLS_VAR(empty_device_cc_instance, value)));
    }
};

exception_type_t
empty_device_cc_instance::issue(transaction_t *t, uint64 addr)
{
    // USER-TODO: Handle accesses to the device here
    if (SIM_transaction_is_read(t)) {
        SIM_LOG_INFO(2, obj(), 0, "read from offset %lld", addr);
        SIM_set_transaction_value_le(t, 0);
    } else {
        SIM_LOG_INFO(2, obj(), 0, "write to offset %lld", addr);
    }
    return Sim_PE_No_Exception;
}

// init_local() is called once when the device module is loaded into Simics
extern "C" void
init_local() try
{
    simics::make_class<empty_device_cc_instance>(
            "empty_device_cc",
            "a C++ device template",
            "This is a documentation string describing the"
            " empty_device_cc class.");
} catch(const std::exception& e) {
    std::cerr << e.what() << std::endl;
}
