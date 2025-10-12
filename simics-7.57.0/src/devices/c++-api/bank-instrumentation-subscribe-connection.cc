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

// Disable warning messages 4503
// Longer than limit decorated have a hash applied and are not
// in danger of a name collision. Not a warning since VS2017
#if defined(_MSC_VER) && _MSC_VER < 1910
#pragma warning(disable : 4503)
#endif

#include "simics/bank-instrumentation-subscribe-connection.h"
#include "simics/type/bank-access.h"

#include <algorithm>  // std::find_if
#include <limits>
#include <utility>
#include <vector>

namespace simics {

static physical_address_t offset(bank_access_t *handle) {
    return *handle->offset;
}

static void set_offset(bank_access_t *handle, physical_address_t offset) {
    *handle->offset = offset;
}

static physical_address_t size(bank_access_t *handle) {
    return handle->size;
}

static bool missed(bank_access_t *handle) {
    return !*handle->success;
}

static void set_missed(bank_access_t *handle, bool missed) {
    *handle->success = !missed;
}

static uint64 value(bank_access_t *handle) {
    return *handle->value;
}

static void set_value(bank_access_t *handle, uint64 value) {
    *handle->value = value;
}

static void inquire(bank_access_t *handle) {
    *handle->inquiry = true;
}

static void suppress(bank_access_t *handle) {
    *handle->suppress = true;
}

static conf_object_t *initiator(bank_access_t *handle) {
    return handle->initiator;
}

template<typename M, typename I>
static void callback(const M &map, I iface, conf_object_t *connection,
                     BankAccess *access) {
    auto c_access = access->c_struct();
    for (auto &it : map) {
        auto item = it.second;
        if ((item.offset == 0 && item.size == 0)
            || (access->offset >= item.offset
                && access->offset < item.offset + item.size)) {
            (item.cb)(connection, &iface, &c_access, item.user_data);
        }
    }
}

BankInstrumentationSubscribeConnection::
BankInstrumentationSubscribeConnection()
    : ar_iface_{offset, size, missed, value, set_missed, set_value, initiator},
      aw_iface_{offset, size, missed, set_missed, initiator},
      br_iface_{offset, size, set_offset, inquire, initiator},
      bw_iface_{offset, size, value, suppress, set_offset, set_value,
                initiator} {
}

bank_callback_handle_t BankInstrumentationSubscribeConnection::
register_after_read(conf_object_t *connection,
                    uint64 offset, uint64 size,
                    after_read_callback_t after_read,
                    lang_void *user_data) {
    init_connection_callbacks(connection);
    AfterRead ar {offset, size, after_read, user_data};
    std::get<ar_map>(connection_callbacks_.back().second).emplace(handle_, ar);
    return handle_++;
}

bank_callback_handle_t BankInstrumentationSubscribeConnection::
register_after_write(conf_object_t *connection,
                     uint64 offset, uint64 size,
                     after_write_callback_t after_write,
                     lang_void *user_data) {
    init_connection_callbacks(connection);
    AfterWrite aw {offset, size, after_write, user_data};
    std::get<aw_map>(connection_callbacks_.back().second).emplace(handle_, aw);
    return handle_++;
}

bank_callback_handle_t BankInstrumentationSubscribeConnection::
register_before_read(conf_object_t *connection,
                     uint64 offset, uint64 size,
                     before_read_callback_t before_read,
                     lang_void *user_data) {
    init_connection_callbacks(connection);
    BeforeRead br {offset, size, before_read, user_data};
    std::get<br_map>(connection_callbacks_.back().second).emplace(handle_, br);
    return handle_++;
}

bank_callback_handle_t BankInstrumentationSubscribeConnection::
register_before_write(conf_object_t *connection,
                      uint64 offset, uint64 size,
                      before_write_callback_t before_write,
                      lang_void *user_data) {
    init_connection_callbacks(connection);
    BeforeWrite bw {offset, size, before_write, user_data};
    std::get<bw_map>(connection_callbacks_.back().second).emplace(handle_, bw);
    return handle_++;
}

void BankInstrumentationSubscribeConnection::
remove_callback(bank_callback_handle_t callback) {
    for (auto itc = connection_callbacks_.begin();
         itc != connection_callbacks_.end();) {
        auto &[_, map_ar, map_aw, map_br, map_bw] = itc->second;
        map_ar.erase(callback);
        map_aw.erase(callback);
        map_br.erase(callback);
        map_bw.erase(callback);
        if (map_ar.empty() && map_aw.empty()
            && map_br.empty() && map_bw.empty())
            itc = connection_callbacks_.erase(itc);
        else
            ++itc;
    }
}

void BankInstrumentationSubscribeConnection::
remove_connection_callbacks(conf_object_t *connection) {
    auto it = find_connection(connection);
    if (it != connection_callbacks_.end()) {
        connection_callbacks_.erase(it);
    }
}

void BankInstrumentationSubscribeConnection::
enable_connection_callbacks(conf_object_t *connection) {
    auto it = find_connection(connection);
    if (it != connection_callbacks_.end()) {
        std::get<bool>(it->second) = true;
    }
}

void BankInstrumentationSubscribeConnection::
disable_connection_callbacks(conf_object_t *connection) {
    auto it = find_connection(connection);
    if (it != connection_callbacks_.end()) {
        std::get<bool>(it->second) = false;
    }
}

attr_value_t BankInstrumentationSubscribeConnection::
get_connections() {
    auto size = connection_callbacks_.size();
    // It is unlikely the number of connections exceeds the maximum
    // supported value
    assert(size <= (std::numeric_limits<unsigned int>::max)());
    attr_value_t connections = SIM_alloc_attr_list(
            static_cast<unsigned int>(size));
    if (size > 0) {
        unsigned int index = 0;
        for (const auto &callback : connection_callbacks_) {
            SIM_attr_list_set_item(&connections, index++,
                                   SIM_make_attr_object(callback.first));
        }
    }
    return connections;
}

bool BankInstrumentationSubscribeConnection::
move_before(conf_object_t *connection, conf_object_t *before) {
    auto it = find_connection(connection);
    if (it == connection_callbacks_.end()) {
        return false;
    }

    // if the before is NULL the connection will be moved last
    if (before == nullptr) {
        std::rotate(it, it + 1, connection_callbacks_.end());
        return true;
    }

    auto it_before = find_connection(before);
    if (it_before == connection_callbacks_.end()) {
        return false;
    }

    auto distance = std::distance(it, it_before);
    if (distance > 1) {
        std::rotate(it, it + 1, it_before);
    } else if (distance < 0) {
        std::rotate(std::make_reverse_iterator(it) - 1,
                    std::make_reverse_iterator(it),
                    std::make_reverse_iterator(it_before));
    }
    return true;
}

void BankInstrumentationSubscribeConnection::
issue_callbacks(BankAccess *access, CallbackType type) const {
    for (auto &itc : connection_callbacks_) {
        conf_object_t *obj = itc.first;
        const auto &[en, map_ar, map_aw, map_br, map_bw] = itc.second;
        if (en == false) {
            continue;
        }
        switch (type) {
        case CallbackType::AR:
            callback<>(map_ar, ar_iface_, obj, access);
            break;
        case CallbackType::AW:
            callback<>(map_aw, aw_iface_, obj, access);
            break;
        case CallbackType::BR:
            callback<>(map_br, br_iface_, obj, access);
            break;
        case CallbackType::BW:
            callback<>(map_bw, bw_iface_, obj, access);
            break;
        default:
            throw std::invalid_argument(
                "Invalid callback type in issue_callbacks");
        }
    }
}

bool BankInstrumentationSubscribeConnection::empty() const {
    return connection_callbacks_.empty();
}

unsigned int BankInstrumentationSubscribeConnection::
number_of_callbacks() const {
    std::vector<conf_obj_cb_pair>::size_type count = 0;
    for (const auto &it : connection_callbacks_) {
        const auto &[_, map_ar, map_aw, map_br, map_bw] = it.second;
        count += map_ar.size() + map_aw.size() \
            + map_br.size() + map_bw.size();
    }
    // It is unlikely to exceed the maximum supported value
    assert(count <= (std::numeric_limits<unsigned int>::max)());
    return static_cast<unsigned int>(count);
}

void BankInstrumentationSubscribeConnection::
init_connection_callbacks(conf_object_t *connection) {
    auto it = find_connection(connection);
    if (it == connection_callbacks_.end()) {
        if (connection) {
            connection_callbacks_.emplace_back(
                    std::make_pair(connection,
                                   std::make_tuple(true, ar_map(), aw_map(),
                                                   br_map(), bw_map())));
        } else {
            connection_callbacks_.emplace(
                    connection_callbacks_.begin(),
                    std::make_pair(connection,
                                   std::make_tuple(true, ar_map(), aw_map(),
                                                   br_map(), bw_map())));
        }
    }
}

BankInstrumentationSubscribeConnection::vect_iter
BankInstrumentationSubscribeConnection::
find_connection(conf_object_t *connection) {
    return std::find_if(connection_callbacks_.begin(),
                        connection_callbacks_.end(),
                        [&connection](const conf_obj_cb_pair &element) {
                            return element.first == connection;
                        });
}

}  // namespace simics
