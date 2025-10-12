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

#include <simics/attr-value.h>
#include <simics/bank-instrumentation-subscribe-connection.h>

#include <gtest/gtest.h>
#include <simics/base/attr-value.h>  // SIM_attr_list_item
#include <simics/type/bank-access.h>

class BankInstrumentationTest : public ::testing::Test {
  public:
    // Counters
    int before_read_cnt = 0;
    int before_write_cnt = 0;
    int after_read_cnt = 0;
    int after_write_cnt = 0;

    // callback information
    physical_address_t callback_offset = 0;
    physical_address_t callback_size = 0;
    bool callback_missed = false;

    size_t access_value = 0;
    conf_object_t *access_initiator = nullptr;

    conf_object_t *registered_connection = nullptr;
    physical_address_t set_offset = 0x40;
    size_t set_value = 0xc0ffee;
    bool set_missed = true;

    simics::BankInstrumentationSubscribeConnection connection;
};

void before_read(conf_object_t *connection,
                 bank_before_read_interface_t* iface,
                 bank_access_t *access, lang_void *user_data) {
    auto *test = static_cast<BankInstrumentationTest*>(user_data);
    test->before_read_cnt++;
    test->registered_connection = connection;
    test->callback_offset = iface->offset(access);
    test->callback_size = iface->size(access);
    test->access_initiator = iface->initiator(access);
    iface->set_offset(access, test->set_offset);
    iface->inquire(access);
}
void before_write(conf_object_t *connection,
                  bank_before_write_interface_t* iface,
                  bank_access_t *access, lang_void *user_data) {
    auto *test = static_cast<BankInstrumentationTest*>(user_data);
    test->before_write_cnt++;
    test->registered_connection = connection;
    test->callback_offset = iface->offset(access);
    test->callback_size = iface->size(access);
    test->access_initiator = iface->initiator(access);
    test->access_value = iface->value(access);
    iface->set_offset(access, test->set_offset);
    iface->set_value(access, test->set_value);
    iface->suppress(access);
}
void after_read(conf_object_t *connection,
                bank_after_read_interface_t* iface,
                bank_access_t *access, lang_void *user_data) {
    auto *test = static_cast<BankInstrumentationTest*>(user_data);
    test->after_read_cnt++;
    test->registered_connection = connection;
    test->callback_offset = iface->offset(access);
    test->callback_size = iface->size(access);
    test->callback_missed = iface->missed(access);
    test->access_initiator = iface->initiator(access);
    iface->set_value(access, test->set_value);
    iface->set_missed(access, test->set_missed);
}
void after_write(conf_object_t *connection,
                 bank_after_write_interface_t* iface,
                 bank_access_t *access, lang_void *user_data) {
    auto *test = static_cast<BankInstrumentationTest*>(user_data);
    test->after_write_cnt++;
    test->registered_connection = connection;
    test->callback_offset = iface->offset(access);
    test->callback_size = iface->size(access);
    test->callback_missed = iface->missed(access);
    test->access_initiator = iface->initiator(access);
    iface->set_missed(access, test->set_missed);
}

TEST(TestBankInstrumentationSubscribeConnection, TestCreationAndDestruction) {
    {
        simics::BankInstrumentationSubscribeConnection connection;
        EXPECT_EQ(connection.empty(), true);
        auto num = connection.number_of_callbacks();
        EXPECT_EQ(num, 0);
        simics::AttrValue connections {connection.get_connections()};
        EXPECT_EQ(SIM_attr_list_size(connections), 0);
    }
}

TEST_F(BankInstrumentationTest, TestRegisterBeforeRead) {
    // Register a before_read callback with offset 0 and size 0x40
    auto handle = connection.register_before_read(nullptr, 0, 0x40,
                                                  before_read, this);
    EXPECT_EQ(handle, 0);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    conf_object_t initiator;
    simics::BankAccess access {nullptr, &initiator, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::BR);
    EXPECT_EQ(before_read_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 4);
    EXPECT_EQ(access_initiator, &initiator);
    EXPECT_EQ(access.offset, set_offset);
    EXPECT_EQ(access.inquiry, true);

    // Missed type
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(before_read_cnt, 1);

    // Missed offset
    access.offset = 0x48;
    connection.issue_callbacks(&access, simics::CallbackType::BR);
    EXPECT_EQ(before_read_cnt, 1);

    // Valid transaction again
    access.offset = 0x16;
    access.size = 2;
    connection.issue_callbacks(&access, simics::CallbackType::BR);
    EXPECT_EQ(before_read_cnt, 2);
    EXPECT_EQ(callback_offset, 0x16);
    EXPECT_EQ(callback_size, 2);
    EXPECT_EQ(access.offset, set_offset);
    EXPECT_EQ(access.inquiry, true);
}

TEST_F(BankInstrumentationTest, TestRegisterBeforeWrite) {
    // Register a before_write callback with offset 0 and size 0x40
    conf_object_t conf_obj;
    auto handle = connection.register_before_write(&conf_obj, 0, 0x40,
                                                   before_write, this);
    EXPECT_EQ(handle, 0);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 8};
    access.value = 0x1234567890abcdef;
    connection.issue_callbacks(&access, simics::CallbackType::BW);
    EXPECT_EQ(before_write_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 8);
    EXPECT_EQ(access_initiator, nullptr);
    EXPECT_EQ(access_value, 0x1234567890abcdef);
    EXPECT_EQ(registered_connection, &conf_obj);
    EXPECT_EQ(access.offset, set_offset);
    EXPECT_EQ(access.value, set_value);
    EXPECT_EQ(access.suppress, true);

    // Missed function
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(before_write_cnt, 1);

    // Missed offset
    access.offset = 0x48;
    connection.issue_callbacks(&access, simics::CallbackType::BW);
    EXPECT_EQ(before_write_cnt, 1);
    access.offset = 0x16;

    // Valid transaction again
    access.size = 2;
    connection.issue_callbacks(&access, simics::CallbackType::BW);
    EXPECT_EQ(before_write_cnt, 2);
    EXPECT_EQ(callback_offset, 0x16);
    EXPECT_EQ(callback_size, 2);
    EXPECT_EQ(registered_connection, &conf_obj);
}

TEST_F(BankInstrumentationTest, TestRegisterAfterRead) {
    // Register a after_read callback with offset 0x12 and size 0x4
    auto handle = connection.register_after_read(nullptr, 0x12, 0x4,
                                                 after_read, this);
    EXPECT_EQ(handle, 0);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    conf_object_t initiator;
    simics::BankAccess access {nullptr, &initiator, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 4);
    EXPECT_EQ(callback_missed, false);
    EXPECT_EQ(access_initiator, &initiator);
    EXPECT_EQ(access.value, set_value);
    EXPECT_EQ(access.success, !set_missed);

    // Missed function
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_read_cnt, 1);

    // Missed offset
    access.offset = 0x48;
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 1);
    access.offset = 0x12;

    // Valid transaction again
    access.size = 2;
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 2);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 2);
}

TEST_F(BankInstrumentationTest, TestRegisterAfterWrite) {
    // Test both offset and size set to 0
    auto handle = connection.register_after_write(nullptr, 0, 0,
                                                  after_write, this);
    EXPECT_EQ(handle, 0);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    conf_object_t initiator;
    simics::BankAccess access {nullptr, &initiator, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 4);
    EXPECT_EQ(callback_missed, false);
    EXPECT_EQ(access_initiator, &initiator);
    EXPECT_EQ(access.success, !set_missed);

    // Missed function
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_write_cnt, 1);

    // Missed offset (Callback is called since both offset and size are 0)
    access.offset = 0x48;
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 2);
    EXPECT_EQ(callback_offset, 0x48);
    EXPECT_EQ(callback_size, 4);

    // Valid transaction again
    access.offset = 0x16;
    access.size = 2;
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 3);
    EXPECT_EQ(callback_offset, 0x16);
    EXPECT_EQ(callback_size, 2);
}

TEST_F(BankInstrumentationTest, TestMultipleRegisterBeforeRead) {
    auto handle = connection.register_before_read(nullptr, 0, 0,
                                                  before_read, this);
    EXPECT_EQ(handle, 0);
    handle = connection.register_before_read(nullptr, 0x12, 0x34,
                                             before_read, this);
    EXPECT_EQ(handle, 1);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 2);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::BR);
    EXPECT_EQ(before_read_cnt, 2);
    EXPECT_EQ(callback_offset, set_offset);
    EXPECT_EQ(callback_size, 4);
}

TEST_F(BankInstrumentationTest, TestMixedRegisterCallbacks) {
    auto handle = connection.register_after_write(nullptr, 0, 0,
                                                  after_write, this);
    EXPECT_EQ(handle, 0);
    handle = connection.register_before_read(nullptr, 0x12, 0x34,
                                             before_read, this);
    EXPECT_EQ(handle, 1);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 2);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 1);
    EXPECT_EQ(before_read_cnt, 0);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 4);

    // Another transaction hit another callback
    connection.issue_callbacks(&access, simics::CallbackType::BR);
    EXPECT_EQ(after_write_cnt, 1);
    EXPECT_EQ(before_read_cnt, 1);
}

TEST_F(BankInstrumentationTest, TestMixedConnectionCallbacks) {
    conf_object_t conf_obj;
    auto handle = connection.register_after_write(&conf_obj, 0x12, 0x34,
                                                  after_write, this);
    EXPECT_EQ(handle, 0);
    handle = connection.register_after_write(nullptr, 0x12, 0x34,
                                             after_write, this);
    EXPECT_EQ(handle, 1);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 2);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 2);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 0x4);
    // NULL connection callbacks called first
    EXPECT_EQ(registered_connection, &conf_obj);
}

TEST_F(BankInstrumentationTest, TestEnableDisableCallbacks) {
    conf_object_t conf_obj;
    auto handle = connection.register_after_read(&conf_obj, 0, 0,
                                                 after_read, this);
    EXPECT_EQ(handle, 0);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 0x4);

    // Disable callbacks
    connection.disable_connection_callbacks(&conf_obj);
    num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 1);

    // Enable callbacks
    connection.enable_connection_callbacks(&conf_obj);
    num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the registered callback
    connection.issue_callbacks(&access, simics::CallbackType::AR);
    EXPECT_EQ(after_read_cnt, 2);
}

TEST_F(BankInstrumentationTest, TestRemoveCallbacks) {
    conf_object_t conf_obj1;
    connection.register_after_write(&conf_obj1, 0x12, 0x34,
                                    after_write, this);
    auto handle = connection.register_after_write(nullptr, 0x12, 0x34,
                                                 after_write, this);
    EXPECT_EQ(handle, 1);
    EXPECT_EQ(connection.empty(), false);
    auto num = connection.number_of_callbacks();
    EXPECT_EQ(num, 2);

    // Remove by handle
    connection.remove_callback(handle);
    num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);

    // A transaction hit the remaining registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    EXPECT_EQ(after_write_cnt, 1);
    EXPECT_EQ(callback_offset, 0x12);
    EXPECT_EQ(callback_size, 0x4);
    // This checks that handle with id 0 is not removed
    EXPECT_EQ(registered_connection, &conf_obj1);

    // Add a new connection callback to test correct one will be
    // removed
    conf_object_t conf_obj2;
    connection.register_after_write(&conf_obj2, 0x12, 0x34,
                                    after_write, this);

    // Remove by connection conf_obj1
    connection.remove_connection_callbacks(&conf_obj1);
    num = connection.number_of_callbacks();
    EXPECT_EQ(num, 1);
    connection.issue_callbacks(&access, simics::CallbackType::AW);
    // Connection conf_obj2 is still there
    EXPECT_EQ(registered_connection, &conf_obj2);

    // Remove by connection conf_obj2
    connection.remove_connection_callbacks(&conf_obj2);
    num = connection.number_of_callbacks();
    EXPECT_EQ(num, 0);
    EXPECT_EQ(connection.empty(), true);
}

TEST(TestBankInstrumentationSubscribeConnection, test_ReorderCallbacks) {
    simics::BankInstrumentationSubscribeConnection connection;

    // Add a non-NULL connection
    conf_object_t *con1 = reinterpret_cast<conf_object_t*>(0xdead);
    connection.register_before_read(con1, 0x12, 0x34, before_read, nullptr);
    EXPECT_EQ(connection.empty(), false);
    simics::AttrValue connections {connection.get_connections()};
    EXPECT_EQ(SIM_attr_list_size(connections), 1);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 0)),
                      con1);

    // NULL connection by default insert in the first place
    connection.register_before_read(nullptr, 0xa0, 0x4, before_read, nullptr);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_list_size(connections), 2);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con1);

    // Non-NULL connection insert at the back
    conf_object_t *con2 = reinterpret_cast<conf_object_t*>(0xbeef);
    connection.register_before_write(con2, 0x10, 0x20, before_write, nullptr);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_list_size(connections), 3);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con1);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con2);

    // move before itself is a nop
    connection.move_before(con1, con1);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_list_size(connections), 3);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con1);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con2);

    // Test move before with non-exist connection
    conf_object_t *con3 = reinterpret_cast<conf_object_t*>(0xc0ffee);
    EXPECT_FALSE(connection.move_before(con3, con1));
    EXPECT_FALSE(connection.move_before(con1, con3));

    // Move the con1 to the end
    connection.move_before(con1, nullptr);
    connections = connection.get_connections();
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con2);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con1);

    // Move the NULL connection before con1
    connection.move_before(nullptr, con1);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 0)),
                      con2);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 1)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con1);

    // Move con2 to the end
    connection.move_before(con2, nullptr);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_list_size(connections), 3);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con1);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con2);

    // Move con2 before con1
    connection.move_before(con2, con1);
    connections = connection.get_connections();
    EXPECT_EQ(SIM_attr_list_size(connections), 3);
    EXPECT_TRUE(SIM_attr_is_nil(SIM_attr_list_item(connections, 0)));
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 1)),
                      con2);
    EXPECT_EQ(SIM_attr_object(SIM_attr_list_item(connections, 2)),
                      con1);
}

TEST(TestBankInstrumentationSubscribeConnection,
     TestIssueCallbacksInvalidType) {
    simics::BankInstrumentationSubscribeConnection connection;
    connection.register_before_read(nullptr, 0x12, 0x34, before_read, this);
    EXPECT_EQ(connection.empty(), false);

    // A transaction hit the registered callback
    simics::BankAccess access {nullptr, nullptr, false, 0x12, 4};
    EXPECT_THROW(
        connection.issue_callbacks(&access,
                                   static_cast<simics::CallbackType>(-1)),
        std::invalid_argument);
}
