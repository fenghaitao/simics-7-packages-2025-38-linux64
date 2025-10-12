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

#ifndef UNITTEST_MOCK_STUBS_H
#define UNITTEST_MOCK_STUBS_H

#include <simics/base/conf-object.h>
#include <simics/base/event.h>
#include <simics/base/map-target.h>
#include <simics/base/sim-exception.h>
#include <simics/simulator/hap-consumer.h>

#include <map>
#include <set>
#include <string>
#include <vector>

struct Stubs {
    Stubs() = default;

    size_t sim_log_info_cnt_ { 0 };
    size_t sim_log_error_cnt_ { 0 };
    size_t sim_log_critical_cnt_ { 0 };
    size_t sim_log_spec_violation_cnt_ { 0 };
    size_t sim_log_unimplemented_cnt_ { 0 };
    size_t sim_log_warning_cnt_ { 0 };

    size_t vt_effective_log_level_ { 0 };

    std::string SIM_log_error_;
    std::string SIM_log_spec_violation_;
    std::string SIM_log_info_;
    std::string SIM_log_unimplemented_;
    std::string SIM_log_critical_;
    std::string SIM_log_warning_;

    void *sim_get_class_data_ret_ { nullptr };

    size_t sim_create_class_cnt_ { 0 };
    const char *sim_create_class_name_ { nullptr };
    class_info_t sim_create_class_class_info_ {};

    void *sim_object_data_ret_ { nullptr };

    size_t sim_set_class_data_cnt_ { 0 };
    conf_class_t *sim_set_class_data_cls_ { nullptr };
    void *sim_set_class_data_data_ { nullptr };

    size_t vt_set_constructor_data_cnt_ { 0 };
    conf_class_t *vt_set_constructor_data_cls_ { nullptr };
    void *vt_set_constructor_data_data_ { nullptr };

    size_t sim_get_class_name_cnt_ { 0 };
    const conf_class_t *sim_get_class_name_cls_ { nullptr };

    size_t sim_register_interface_cnt_ { 0 };
    std::map<std::string, const interface_t *> sim_register_interface_map_;
    int sim_register_interface_ret_ {0};

    size_t sim_log_register_groups_cnt_ { 0 };

    size_t sim_register_port_cnt_ { 0 };
    conf_class_t *sim_register_port_port_cls_ { nullptr };
    std::string sim_register_port_name_ {};

    conf_class_t *a_conf_class_ { nullptr };
    const char *a_const_char { "" };
    int a_int { 0 };

    std::map<const conf_object_t *, const char *> sim_object_name_;

    conf_object_t *sim_port_object_parent_ret_ { nullptr };
    std::map<std::string, interface_t *> sim_c_get_port_interface_map_;

    bool sim_transaction_is_write_ { false };
    bool sim_transaction_is_read_ { false };
    bool sim_transaction_is_inquiry_ { false };
    conf_object_t *sim_transaction_initiator_ { nullptr };
    std::vector<unsigned char>::size_type sim_transaction_size_ {0};
    buffer_t sim_get_transaction_bytes_;

    conf_object_t *sim_object_descendant_ret_ { nullptr };

    bool sim_marked_for_deletion_ret_ {false};
    bool sim_object_is_configured_ret_ {false};
    bool sim_class_has_attribute_ret_ {false};
    conf_class_t *sim_class_port_ret_ {nullptr};

    size_t sim_notify_cnt_ { 0 };

    size_t sim_register_attribute_cnt_ { 0 };
    size_t sim_register_attribute_with_user_data_cnt_ { 0 };
    size_t sim_register_class_attribute_cnt_ { 0 };
    size_t sim_register_event_cnt_ { 0 };
    std::set<std::string> sim_register_attribute_with_user_data_names_;
    attr_value_t (*last_get_attr_with_user_data_)(
            conf_object_t *, lang_void *) {nullptr};  // NOLINT
    set_error_t (*last_set_attr_with_user_data_)(conf_object_t *,
            attr_value_t *, lang_void *) {nullptr};  // NOLINT
    std::string sim_register_attribute_with_user_data_type_ {""};
    sim_exception_t sim_clear_exception_ret_;
    const char *sim_last_error_ret_ { "" };
    attr_value_t sim_get_attribute_ret_ {};

    // Event related
    event_class_t *sim_register_event_ret_ {nullptr};
    conf_object_t *object_clock_ret_ {nullptr};
    event_class_t *event_cancel_time_evclass_ {nullptr};
    conf_object_t *event_cancel_time_obj_ {nullptr};
    void *event_cancel_time_data_ {nullptr};
    double event_find_next_time_ret_ {-1.0};
    event_class_t *event_post_time_evclass_ {nullptr};
    conf_object_t *event_post_time_obj_ {nullptr};
    double event_post_time_seconds_ {0.0};
    void *event_post_time_user_data_ {nullptr};
    int event_find_next_cycle_ret_ {-1};
    event_class_t *event_post_cycle_evclass_ {nullptr};
    conf_object_t *event_post_cycle_obj_ {nullptr};
    cycles_t event_post_cycle_cycles_ {0};
    void *event_post_cycle_user_data_ {nullptr};
    event_class_t *event_cancel_step_evclass_ {nullptr};
    conf_object_t *event_cancel_step_obj_ {nullptr};
    void *event_cancel_step_data_ {nullptr};
    pc_step_t event_find_next_step_ret_ {-1};
    event_class_t *event_post_step_evclass_ {nullptr};
    conf_object_t *event_post_step_obj_ {nullptr};
    pc_step_t event_post_step_steps_ {0};
    void *event_post_step_user_data_ {nullptr};

    conf_object_t sim_obj_;

    size_t sim_attr_free_cnt_ {0};

    map_target_t *new_map_target_ret_ {nullptr};
    size_t sim_free_map_target_cnt_ {0};
    exception_type_t issue_transaction_ret_ {Sim_PE_No_Exception};
    uint64 get_transaction_value_le_ret_ {0};

    conf_object_t *sim_require_object_obj_ {nullptr};
    const conf_object_t *sim_object_is_configured_obj_ {nullptr};

    attr_value_t sim_get_class_attribute_ret_ {};
    const char *sim_attribute_error_msg_ {""};
    event_class_t *sim_get_event_class_ret_ {nullptr};

    obj_hap_func_t sim_hap_callback_func_ {nullptr};
    static Stubs instance_;
};

#endif
