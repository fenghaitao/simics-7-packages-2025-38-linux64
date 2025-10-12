// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <gtest/gtest.h>
#include <string>

#include "simics/log.h"

#include "mock/stubs.h"

// Test cases for ConfObjectRef
class LogTest : public ::testing::Test {
  protected:
    conf_object_t mock_conf_object;
    const std::string mock_str = "test_str";

    LogTest() {}

    void SetUp() override {
        Stubs::instance_.sim_log_info_cnt_ = 0;
        Stubs::instance_.sim_log_error_cnt_ = 0;
        Stubs::instance_.sim_log_critical_cnt_ = 0;
        Stubs::instance_.sim_log_spec_violation_cnt_ = 0;
        Stubs::instance_.sim_log_unimplemented_cnt_ = 0;
        Stubs::instance_.sim_log_warning_cnt_ = 0;
        Stubs::instance_.SIM_log_error_.clear();
        Stubs::instance_.SIM_log_spec_violation_.clear();
        Stubs::instance_.SIM_log_info_.clear();
        Stubs::instance_.SIM_log_unimplemented_.clear();
        Stubs::instance_.SIM_log_critical_.clear();
        Stubs::instance_.SIM_log_warning_.clear();
    }

    void TearDown() override {
        Stubs::instance_.sim_log_info_cnt_ = 0;
        Stubs::instance_.sim_log_error_cnt_ = 0;
        Stubs::instance_.sim_log_critical_cnt_ = 0;
        Stubs::instance_.sim_log_spec_violation_cnt_ = 0;
        Stubs::instance_.sim_log_unimplemented_cnt_ = 0;
        Stubs::instance_.sim_log_warning_cnt_ = 0;
        Stubs::instance_.SIM_log_error_.clear();
        Stubs::instance_.SIM_log_spec_violation_.clear();
        Stubs::instance_.SIM_log_info_.clear();
        Stubs::instance_.SIM_log_unimplemented_.clear();
        Stubs::instance_.SIM_log_critical_.clear();
        Stubs::instance_.SIM_log_warning_.clear();
    }
};

TEST_F(LogTest, INFO_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_info_.empty());
    SIM_LOG_INFO_STR(3, &mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, mock_str);
}

TEST_F(LogTest, ERROR_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_error_.empty());
    SIM_LOG_ERROR_STR(&mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, mock_str);
}

TEST_F(LogTest, CRITICAL_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_critical_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_critical_.empty());
    SIM_LOG_CRITICAL_STR(&mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_critical_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_critical_, mock_str);
}

TEST_F(LogTest, SPEC_VIOLATION_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_spec_violation_.empty());
    SIM_LOG_SPEC_VIOLATION_STR(1, &mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_, mock_str);
}

TEST_F(LogTest, UNIMPLEMENTED_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_unimplemented_.empty());
    SIM_LOG_UNIMPLEMENTED_STR(4, &mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_, mock_str);
}

TEST_F(LogTest, WARNING_MACRO) {
    EXPECT_EQ(Stubs::instance_.sim_log_warning_cnt_, 0);
    EXPECT_TRUE(Stubs::instance_.SIM_log_warning_.empty());
    SIM_LOG_WARNING_STR(&mock_conf_object, 0, mock_str);
    EXPECT_EQ(Stubs::instance_.sim_log_warning_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_warning_, mock_str);
}
