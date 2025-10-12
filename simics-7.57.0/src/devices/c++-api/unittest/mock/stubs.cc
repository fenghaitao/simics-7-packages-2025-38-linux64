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

#include "stubs.h"

#include <simics/base/conf-object.h>
#include <simics/base/transaction.h>
#include <simics/base/log.h>
#include <simics/base/notifier.h>

#include <cstdio>
#include <string>

#include "mock-object.h"

// Stubs that define symbol
extern "C" {
void *SIM_get_class_data(conf_class_t *cls) {
    return Stubs::instance_.sim_get_class_data_ret_;
}

conf_class_t *SIM_create_class(const char *name,
                               const class_info_t *class_info) {
    ++Stubs::instance_.sim_create_class_cnt_;
    Stubs::instance_.sim_create_class_name_ = name;
    Stubs::instance_.sim_create_class_class_info_ = *class_info;
    return Stubs::instance_.a_conf_class_;
}

void *SIM_object_data(conf_object_t *obj) {
    return Stubs::instance_.sim_object_data_ret_;
}

void SIM_set_class_data(conf_class_t *cls, void *data) {
    ++Stubs::instance_.sim_set_class_data_cnt_;
    Stubs::instance_.sim_set_class_data_cls_ = cls;
    Stubs::instance_.sim_set_class_data_data_ = data;
}

void VT_set_constructor_data(conf_class_t *cls, void *data) {
    ++Stubs::instance_.vt_set_constructor_data_cnt_;
    Stubs::instance_.vt_set_constructor_data_cls_ = cls;
    Stubs::instance_.vt_set_constructor_data_data_ = data;
}

const char *SIM_get_class_name(const conf_class_t *cls) {
    ++Stubs::instance_.sim_get_class_name_cnt_;
    Stubs::instance_.sim_get_class_name_cls_ = cls;
    return Stubs::instance_.a_const_char;
}

void SIM_log_register_groups(conf_class_t *cls,
                             const char *const *names) {
    ++Stubs::instance_.sim_log_register_groups_cnt_;
}

int SIM_register_interface(conf_class_t *cls, const char *name,
                           const interface_t *iface) {
    ++Stubs::instance_.sim_register_interface_cnt_;
    Stubs::instance_.sim_register_interface_map_[name] = iface;
    return Stubs::instance_.sim_register_interface_ret_;
}

void SIM_register_port(conf_class_t *cls, const char *name,
                       conf_class_t *port_cls, const char *desc) {
    ++Stubs::instance_.sim_register_port_cnt_;
    Stubs::instance_.sim_register_port_port_cls_ = port_cls;
    Stubs::instance_.sim_register_port_name_ = name;
}

api_function_t SIM_get_api_function(const char *function) {
    return nullptr;
}

NORETURN void VT_report_bad_attr_type(const char *function, attr_kind_t wanted,
                                      attr_value_t actual) {
    // NORETURN
    while (1)
        continue;
}
NORETURN void VT_bad_attr_type(const char *function, attr_kind_t wanted,
                               attr_value_t actual) {
    // NORETURN
    while (1)
        continue;
}

attr_value_t SIM_make_attr_string(const char *str) {
    if (!str)
        return SIM_make_attr_nil();

    attr_value_t ret;
    ret.private_kind = Sim_Val_String;
    size_t size = strlen(str) + 1;
    char *p = new char[size];
    memcpy(p, str, size);
    ret.private_u.string = p;
    return ret;
}

attr_value_t SIM_make_attr_data(size_t size, const void *data) {
    attr_value_t res;
    res.private_kind = Sim_Val_Data;
    res.private_size = static_cast<unsigned>(size);
    res.private_u.data = static_cast<uint8 *>(const_cast<void *>(data));
    return res;
}

attr_value_t SIM_alloc_attr_list(unsigned length) {
    attr_value_t res;
    res.private_kind = Sim_Val_List;
    res.private_size = length;
    res.private_u.list = new attr_value_t[length];
    return res;
}

void SIM_attr_list_set_item(attr_value_t *NOTNULL attr, unsigned index,
                            attr_value_t elem) {
    attr->private_u.list[index] = elem;
}

strbuf_t sb_newf(const char *format, ...) {
    return SB_INIT;
}

NORETURN void assert_error(int line, const char *file,
                           const char *mod_date, const char *message) {
    while (1)
        continue;
}

const char *SIM_object_name(const conf_object_t *NOTNULL obj) {
    return Stubs::instance_.sim_object_name_[obj];
}

void SIM_require_object(conf_object_t *NOTNULL obj) {
    Stubs::instance_.sim_require_object_obj_ = obj;
}

conf_object_t *SIM_port_object_parent(conf_object_t *NOTNULL obj) {
    return Stubs::instance_.sim_port_object_parent_ret_;
}

const interface_t *SIM_c_get_port_interface(const conf_object_t *NOTNULL obj,
                                            const char *NOTNULL name,
                                            const char *portname) {
    std::string name_str;
    if (portname) {
        name_str.append(portname);
        name_str.append(".");
        name_str.append(name);
    } else {
        name_str.append(name);
    }
    if (Stubs::instance_.sim_c_get_port_interface_map_.find(name_str)
        != Stubs::instance_.sim_c_get_port_interface_map_.end()) {
        return Stubs::instance_.sim_c_get_port_interface_map_.at(name_str);
    } else {
        return nullptr;
    }
}

unsigned SIM_transaction_size(const transaction_t *NOTNULL t) {
    return static_cast<unsigned>(Stubs::instance_.sim_transaction_size_);
}

conf_object_t *SIM_transaction_initiator(const transaction_t *NOTNULL t) {
    return Stubs::instance_.sim_transaction_initiator_;
}

bool SIM_transaction_is_write(const transaction_t *NOTNULL t) {
    return Stubs::instance_.sim_transaction_is_write_;
}

void SIM_get_transaction_bytes(const transaction_t *NOTNULL t,
                               buffer_t bytes) {
    assert(bytes.len == Stubs::instance_.sim_get_transaction_bytes_.len);
    for (size_t i = 0; i < bytes.len; ++i) {
        bytes.data[i] = Stubs::instance_.sim_get_transaction_bytes_.data[i];
    }
}

bool SIM_transaction_is_inquiry(const transaction_t *NOTNULL t) {
    return Stubs::instance_.sim_transaction_is_inquiry_;
}

bool SIM_transaction_is_read(const transaction_t *NOTNULL t) {
    return Stubs::instance_.sim_transaction_is_read_;
}

void SIM_set_transaction_bytes(const transaction_t *NOTNULL t,
                               bytes_t bytes) {
}

conf_object_t *SIM_object_descendant(conf_object_t *obj,
                                     const char *NOTNULL relname) {
    return Stubs::instance_.sim_object_descendant_ret_;
}

unsigned SIM_log_level(const conf_object_t *NOTNULL obj) {
    return 4;
}

void SIM_c_attribute_error(const char *NOTNULL msg, ...) {
}


int SIM_hap_add_callback_obj(const char *NOTNULL hap,
                             conf_object_t *NOTNULL obj,
                             int flags,
                             NOTNULL obj_hap_func_t func,
                             lang_void *data) {
    Stubs::instance_.sim_hap_callback_func_ = func;
    return 0;
}

void SIM_hap_delete_callback_obj(const char *NOTNULL hap,
                                 conf_object_t *NOTNULL obj,
                                 NOTNULL obj_hap_func_t func, lang_void *data) {
}

void SIM_notify(conf_object_t *NOTNULL obj, notifier_type_t type) {
    ++Stubs::instance_.sim_notify_cnt_;
}

void SIM_register_notifier(conf_class_t *NOTNULL cls,
                           notifier_type_t what,
                           const char *desc) {
    // Not used by Simics Base; left empty for now
}

#define LOG_TO_STRING()                   \
    char buf[1024];                       \
    va_list va = {};                           \
    va_start(va, str);                    \
    vsnprintf(buf, sizeof(buf), str, va); \
    va_end(va);                           \
    buf[1023] = 0;

void SIM_log_info(int lvl, conf_object_t *dev, int grp,
                  const char *str, ...) {
    ++Stubs::instance_.sim_log_info_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_info_ = buf;
}

void SIM_log_error(conf_object_t *dev, int grp, const char *str, ...) {
    ++Stubs::instance_.sim_log_error_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_error_ = buf;
}

void VT_log_critical(conf_object_t *NOTNULL dev, uint64 grp,
                     const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_critical_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_critical_ = buf;
}

void VT_log_spec_violation(int lvl, conf_object_t *NOTNULL dev,
                           uint64 grp, const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_spec_violation_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_spec_violation_ = buf;
}

void VT_log_info(int lvl, conf_object_t *NOTNULL dev, uint64 grp,
                 const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_info_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_info_ = buf;
}

void VT_log_unimplemented(int lvl, conf_object_t *NOTNULL dev, uint64 grp,
                          const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_unimplemented_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_unimplemented_ = buf;
}

void VT_log_error(conf_object_t *NOTNULL dev, uint64 grp,
                  const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_error_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_error_ = buf;
}

void VT_log_warning(conf_object_t *NOTNULL dev, uint64 grp,
                    const char *NOTNULL str, ...) {
    ++Stubs::instance_.sim_log_warning_cnt_;
    LOG_TO_STRING();
    Stubs::instance_.SIM_log_warning_ = buf;
}

void SIM_log_message_vararg(conf_object_t *obj, int level, uint64 group_ids,
                            log_type_t log_type, const char *str, ...) {
    switch (log_type) {
        case Sim_Log_Info: {
            ++Stubs::instance_.sim_log_info_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_info_ = buf;
        }
        break;
        case Sim_Log_Error: {
            ++Stubs::instance_.sim_log_error_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_error_ = buf;
        }
        break;
        case Sim_Log_Spec_Violation: {
            ++Stubs::instance_.sim_log_spec_violation_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_spec_violation_ = buf;
        }
        break;
        case Sim_Log_Unimplemented: {
            ++Stubs::instance_.sim_log_unimplemented_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_unimplemented_ = buf;
        }
        break;
        case Sim_Log_Critical: {
            ++Stubs::instance_.sim_log_critical_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_critical_ = buf;
        }
        break;
        case Sim_Log_Warning: {
            ++Stubs::instance_.sim_log_warning_cnt_;
            LOG_TO_STRING();
            Stubs::instance_.SIM_log_warning_ = buf;
        }
        break;
        default:
            break;
    }
}

unsigned VT_effective_log_level(const conf_object_t *NOTNULL obj) {
    ++Stubs::instance_.vt_effective_log_level_;
    return 4;
}

bool SIM_marked_for_deletion(const conf_object_t *NOTNULL obj) {
    return Stubs::instance_.sim_marked_for_deletion_ret_;
}

bool SIM_object_is_configured(const conf_object_t *NOTNULL obj) {
    Stubs::instance_.sim_object_is_configured_obj_ = obj;
    return Stubs::instance_.sim_object_is_configured_ret_;
}

bool SIM_class_has_attribute(conf_class_t *NOTNULL cls,
                             const char *NOTNULL attr) {
    return Stubs::instance_.sim_register_attribute_with_user_data_names_.find(
            attr)
        != Stubs::instance_.sim_register_attribute_with_user_data_names_.end();
}

conf_class_t *SIM_class_port(const conf_class_t *NOTNULL cls,
                             const char *NOTNULL name) {
    return Stubs::instance_.sim_class_port_ret_;
}

void SIM_register_attribute(
        conf_class_t *NOTNULL cls, const char *NOTNULL name,
        attr_value_t (*get_attr)(conf_object_t *),
        set_error_t (*set_attr)(conf_object_t *, attr_value_t *),
        attr_attr_t attr, const char *type, const char *desc) {
    ++Stubs::instance_.sim_register_attribute_cnt_;
}

void SIM_register_attribute_with_user_data(
        conf_class_t *NOTNULL cls, const char *NOTNULL name,
        attr_value_t (*get_attr)(conf_object_t *, lang_void *),
        lang_void *user_data_get,
        set_error_t (*set_attr)(conf_object_t *, attr_value_t *, lang_void *),
        lang_void *user_data_set,
        attr_attr_t attr, const char *NOTNULL type, const char *desc) {
    ++Stubs::instance_.sim_register_attribute_with_user_data_cnt_;
    Stubs::instance_.sim_register_attribute_with_user_data_names_.insert(
            name);
    Stubs::instance_.last_get_attr_with_user_data_ = get_attr;
    Stubs::instance_.last_set_attr_with_user_data_ = set_attr;
    Stubs::instance_.sim_register_attribute_with_user_data_type_ = type;
}

sim_exception_t SIM_clear_exception(void) {
    sim_exception_t ret = Stubs::instance_.sim_clear_exception_ret_;
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_No_Exception;
    return ret;
}

const char *SIM_last_error(void) {
    return Stubs::instance_.sim_last_error_ret_;
}

attr_value_t SIM_get_attribute(conf_object_t *NOTNULL obj,
                               const char *NOTNULL name) {
    return Stubs::instance_.sim_get_attribute_ret_;
}

conf_object_t *SIM_get_object(const char *name) {
    if (strcmp(name, "sim") == 0)
        return &Stubs::instance_.sim_obj_;

    return nullptr;
}

event_class_t *SIM_register_event(
        const char *NOTNULL name,
        conf_class_t *cl,
        event_class_flag_t flags,
        void (*NOTNULL callback)(conf_object_t *obj, lang_void *data),
        void (*destroy)(conf_object_t *obj, lang_void *data),
        attr_value_t (*get_value)(conf_object_t *obj, lang_void *data),
        lang_void *(*set_value)(conf_object_t *obj, attr_value_t value),
        char *(*describe)(conf_object_t *obj, lang_void *data)) {
    ++Stubs::instance_.sim_register_event_cnt_;
    return Stubs::instance_.sim_register_event_ret_;
}

void SIM_event_post_time(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj, double seconds, lang_void *user_data) {
    Stubs::instance_.event_post_time_evclass_ = evclass;
    Stubs::instance_.event_post_time_obj_ = obj;
    Stubs::instance_.event_post_time_seconds_ = seconds;
    Stubs::instance_.event_post_time_user_data_ = user_data;
}

void SIM_event_post_cycle(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj, cycles_t cycles, lang_void *user_data) {
    Stubs::instance_.event_post_cycle_evclass_ = evclass;
    Stubs::instance_.event_post_cycle_obj_ = obj;
    Stubs::instance_.event_post_cycle_cycles_ = cycles;
    Stubs::instance_.event_post_cycle_user_data_ = user_data;
}

void SIM_event_post_step(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj, pc_step_t cycles, lang_void *user_data) {
    Stubs::instance_.event_post_step_evclass_ = evclass;
    Stubs::instance_.event_post_step_obj_ = obj;
    Stubs::instance_.event_post_step_steps_ = cycles;
    Stubs::instance_.event_post_step_user_data_ = user_data;
}

void SIM_event_cancel_time(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj,
        int (*pred)(lang_void *data, lang_void *match_data),
        lang_void *match_data) {
    Stubs::instance_.event_cancel_time_evclass_ = evclass;
    Stubs::instance_.event_cancel_time_obj_ = obj;
    Stubs::instance_.event_cancel_time_data_ = match_data;
}

void SIM_event_cancel_step(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj,
        int (*pred)(lang_void *data, lang_void *match_data),
        lang_void *match_data) {
    Stubs::instance_.event_cancel_step_evclass_ = evclass;
    Stubs::instance_.event_cancel_step_obj_ = obj;
    Stubs::instance_.event_cancel_step_data_ = match_data;
}

double SIM_event_find_next_time(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj,
        int (*pred)(lang_void *data, lang_void *match_data),
        lang_void *match_data) {
    return Stubs::instance_.event_find_next_time_ret_;
}

cycles_t SIM_event_find_next_cycle(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj,
        int (*pred)(lang_void *data, lang_void *match_data),
        lang_void *match_data) {
    return Stubs::instance_.event_find_next_cycle_ret_;
}

pc_step_t SIM_event_find_next_step(
        conf_object_t *NOTNULL clock, event_class_t *NOTNULL evclass,
        conf_object_t *NOTNULL obj,
        int (*pred)(lang_void *data, lang_void *match_data),
        lang_void *match_data) {
    return Stubs::instance_.event_find_next_step_ret_;
}

conf_object_t *SIM_object_clock(const conf_object_t *NOTNULL obj) {
    return Stubs::instance_.object_clock_ret_;
}

void SIM_attr_free(attr_value_t *value) {
    if (value->private_kind == Sim_Val_List) {
        for (size_t index = 0; index < value->private_size; ++index) {
            SIM_attr_free(&(value->private_u.list[index]));
        }
        delete[] value->private_u.list;
    }
    if (value->private_kind == Sim_Val_String) {
        delete[] value->private_u.string;
    }
    value->private_kind = Sim_Val_Invalid;
    ++Stubs::instance_.sim_attr_free_cnt_;
}

attr_value_t SIM_attr_copy(attr_value_t val) {
    return val;
}

map_target_t *SIM_new_map_target(conf_object_t *NOTNULL obj, const char *port,
                                 const map_target_t *chained_target) {
    if (obj == nullptr) {
        return nullptr;
    }
    return Stubs::instance_.new_map_target_ret_;
}

void SIM_free_map_target(map_target_t *mt) {
    ++Stubs::instance_.sim_free_map_target_cnt_;
    if (mt == Stubs::instance_.new_map_target_ret_) {
        Stubs::instance_.new_map_target_ret_ = nullptr;
    }
}

exception_type_t SIM_issue_transaction(const map_target_t *NOTNULL mt,
                                       transaction_t *NOTNULL t, uint64 addr) {
    return Stubs::instance_.issue_transaction_ret_;
}

uint64 SIM_get_transaction_value_le(const transaction_t *NOTNULL t) {
    return Stubs::instance_.get_transaction_value_le_ret_;
}

void SIM_set_transaction_value_le(const transaction_t *NOTNULL t,
                                  uint64 val) {}
}

void SIM_register_class_attribute(conf_class_t *NOTNULL cls,
                                  const char *NOTNULL name,
                                  attr_value_t (*get_attr)(conf_class_t *),
                                  set_error_t (*set_attr)(conf_class_t *,
                                                          attr_value_t *),
                                  attr_attr_t attr, const char *type,
                                  const char *desc) {
    ++Stubs::instance_.sim_register_class_attribute_cnt_;
}

attr_value_t SIM_get_class_attribute(conf_class_t *NOTNULL cls,
                                     const char *NOTNULL name) {
    return Stubs::instance_.sim_get_class_attribute_ret_;
}

void SIM_attribute_error(const char *NOTNULL msg) {
    Stubs::instance_.sim_attribute_error_msg_ = msg;
}

event_class_t *SIM_get_event_class(conf_class_t *NOTNULL cl,
                                   const char *NOTNULL name) {
    return Stubs::instance_.sim_get_event_class_ret_;
}

Stubs Stubs::instance_;
size_t MockObject::instance_cnt_ { 0 };
size_t MockObject::init_class_cnt_ { 0 };
size_t MockObjectWithArg::instance_cnt_ { 0 };
size_t MockObjectWithArg::init_class_cnt_ { 0 };
