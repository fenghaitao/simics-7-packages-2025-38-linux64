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

#include <simics/type/bank-access.h>

#include <gtest/gtest.h>

#include "mock/mock-object.h"
#include "mock/stubs.h"

TEST(TestBankAccess, TestBankAccessCreation) {
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = 2;
    Stubs::instance_.sim_transaction_initiator_ = reinterpret_cast<
        conf_object_t *>(uintptr_t{0xdeadbeef});
    transaction_t t;

    MockObject mock_obj {reinterpret_cast<conf_object_t *>(0x1234)};

    simics::BankAccess access {mock_obj.obj().object(), &t, 0xc0ffee};
    EXPECT_EQ(access.bank, mock_obj.obj().object());
    EXPECT_EQ(access.inquiry,
                      Stubs::instance_.sim_transaction_is_inquiry_);
    EXPECT_EQ(access.offset, 0xc0ffee);
    EXPECT_EQ(access.size, 2);
    EXPECT_EQ(access.value, 0);
    EXPECT_EQ(access.success, true);
    EXPECT_EQ(access.suppress, false);
    EXPECT_EQ(access.initiator,
                      Stubs::instance_.sim_transaction_initiator_);

    auto c_access = access.c_struct();
    EXPECT_EQ(c_access.bank, access.bank);
    EXPECT_EQ(c_access.initiator, access.initiator);
    EXPECT_EQ(c_access.offset, &access.offset);
    EXPECT_EQ(c_access.size, access.size);
    EXPECT_EQ(c_access.value, &access.value);
    EXPECT_EQ(c_access.success, &access.success);
    EXPECT_EQ(c_access.suppress, &access.suppress);
}
