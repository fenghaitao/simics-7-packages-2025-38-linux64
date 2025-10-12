// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_BANK_INSTRUMENTATION_SUBSCRIBE_CONNECTION_H
#define SIMICS_BANK_INSTRUMENTATION_SUBSCRIBE_CONNECTION_H

#include <simics/c++/model-iface/bank-instrumentation.h>
#include <simics/c++/model-iface/instrumentation-provider.h>

#include <cstdint>
#include <map>
#include <tuple>
#include <utility>
#include <vector>

#include "simics/bank-issue-callbacks-interface.h"

namespace simics {

struct BankAccess;

// Instrumentation connection and callback manager
// According to API reference manual about "instrumentation_order":
// The default order for callbacks that should be honored by all providers,
// where possible, regardless if they implement the instrumentation_order
// interface or not is:
// 1. all anonymous connections, i.e. NULL connections,
// 2. in registration order connection order, which if not re-ordered will be
//    the connection registration order
// 3. callback registration order
class BankInstrumentationSubscribeConnection
    : public iface::BankInstrumentationSubscribeInterface,
      public iface::InstrumentationOrderInterface,
      public BankIssueCallbacksInterface {
    struct AfterRead {
        uint64_t offset;
        uint64_t size;
        after_read_callback_t cb;
        lang_void *user_data;
    };
    struct AfterWrite {
        uint64_t offset;
        uint64_t size;
        after_write_callback_t cb;
        lang_void *user_data;
    };
    struct BeforeRead {
        uint64_t offset;
        uint64_t size;
        before_read_callback_t cb;
        lang_void *user_data;
    };
    struct BeforeWrite {
        uint64_t offset;
        uint64_t size;
        before_write_callback_t cb;
        lang_void *user_data;
    };
    using ar_map = std::map<bank_callback_handle_t, AfterRead>;
    using aw_map = std::map<bank_callback_handle_t, AfterWrite>;
    using br_map = std::map<bank_callback_handle_t, BeforeRead>;
    using bw_map = std::map<bank_callback_handle_t, BeforeWrite>;
    using cb_tuple = std::tuple<bool, ar_map, aw_map, br_map, bw_map>;
    using conf_obj_cb_pair = std::pair<conf_object_t *, cb_tuple>;
    using vect_iter = std::vector<conf_obj_cb_pair>::iterator;

  public:
    BankInstrumentationSubscribeConnection();
    virtual ~BankInstrumentationSubscribeConnection() = default;

    // iface::BankInstrumentationInterface
    bank_callback_handle_t register_after_read(
            conf_object_t *connection, uint64 offset, uint64 size,
            after_read_callback_t after_read, lang_void *user_data) override;
    bank_callback_handle_t register_after_write(
            conf_object_t *connection, uint64 offset, uint64 size,
            after_write_callback_t after_write, lang_void *user_data) override;
    bank_callback_handle_t register_before_read(
            conf_object_t *connection, uint64 offset, uint64 size,
            before_read_callback_t before_read, lang_void *user_data) override;
    bank_callback_handle_t register_before_write(
            conf_object_t *connection, uint64 offset, uint64 size,
            before_write_callback_t before_write,
            lang_void *user_data) override;
    void remove_callback(bank_callback_handle_t callback) override;
    void remove_connection_callbacks(conf_object_t *connection) override;
    void enable_connection_callbacks(conf_object_t *connection) override;
    void disable_connection_callbacks(conf_object_t *connection) override;

    // iface::InstrumentationOrderInterface
    attr_value_t get_connections() override;
    bool move_before(conf_object_t *connection, conf_object_t *before) override;

    // iface::BankIssueCallbacksInterface
    void issue_callbacks(BankAccess *access, CallbackType type) const override;

    // Helper functions
    bool empty() const;
    // The total number of callbacks saved
    unsigned int number_of_callbacks() const;

  private:
    void init_connection_callbacks(conf_object_t *connection);
    vect_iter find_connection(conf_object_t *connection);

    // Initialized once and used inside each tool callback to monitor and
    // modify the state of current accesses
    bank_after_read_interface_t ar_iface_;
    bank_after_write_interface_t aw_iface_;
    bank_before_read_interface_t br_iface_;
    bank_before_write_interface_t bw_iface_;

    bank_callback_handle_t handle_ {0};
    std::vector<conf_obj_cb_pair> connection_callbacks_;
};

}  // namespace simics

#endif
