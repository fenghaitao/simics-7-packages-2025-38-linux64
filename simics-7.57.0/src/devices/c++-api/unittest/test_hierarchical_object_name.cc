// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/type/hierarchical-object-name.h>

#include <gtest/gtest.h>

#include <string>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW

using simics::detail::HierarchicalObjectName;

TEST(TestValidateName, ValidNames) {
    // Test valid names
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("ValidName"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid_Name"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid123"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid_Name123"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid[2]"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid[2 32]"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name(
        "Valid[2 stride 32]"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name("Valid[2][3]"));
    EXPECT_NO_THROW(HierarchicalObjectName::validate_name(
        "Valid[2 stride 16][3]"));
}

TEST(TestValidateName, EmptyName) {
    // Test empty name
    EXPECT_THROW(
        HierarchicalObjectName::validate_name(""),
        std::invalid_argument);
}

TEST(TestValidateName, InvalidStartingCharacter) {
    // Test names that do not start with an alphabetic character
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("1InvalidName"),
        std::invalid_argument);
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("_InvalidName"),
        std::invalid_argument);
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("$InvalidName"),
        std::invalid_argument);
}

TEST(TestValidateName, InvalidCharacters) {
    // Test names with invalid characters
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("Invalid Name"),
        std::invalid_argument);
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("Invalid@Name"),
        std::invalid_argument);
    EXPECT_THROW(
        HierarchicalObjectName::validate_name("Invalid#Name"),
        std::invalid_argument);
}

TEST(TestHierarchicalObjectName, TestCTOR) {
    {
        // CTOR takes a const char*
        const char *some_chars = "some_chars";
        HierarchicalObjectName n {some_chars};
        EXPECT_EQ(n.base_name(), "some_chars");
    }
    {
        // CTOR takes a const char* and a size
        const char *some_chars = "first_5";
        HierarchicalObjectName n {some_chars, 5};
        EXPECT_EQ(n.base_name(), "first");
    }
    {
        // CTOR takes same type
        HierarchicalObjectName some_string_view {"same_type"};
        HierarchicalObjectName n {some_string_view};
        EXPECT_EQ(n.base_name(), "same_type");
    }
}

bool NameEmpty(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
              "Empty name is not allowed");
    return true;
}

template<const char *C>
bool NameHasInvalidCharacter(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
              std::string("Character (") + C \
              + ") is not allowed to use in a name");
    return true;
}

TEST(TestHierarchicalObjectName, TestCTORException) {
    {
        EXPECT_PRED_THROW(HierarchicalObjectName n(""),
                          std::invalid_argument, NameEmpty);
    }
    EXPECT_PRED_THROW(HierarchicalObjectName n("3x"),
                      std::invalid_argument,
                      [](const std::exception &ex) {
        auto message = std::string(ex.what());
        EXPECT_EQ(message.substr(0, message.rfind(':')),
                  "Name (3x) does not begin with an alphabetic character");
                      });

    constexpr static char space[] = " ";
    EXPECT_PRED_THROW(HierarchicalObjectName n("x "),
                      std::invalid_argument, NameHasInvalidCharacter<space>);
    constexpr static char dollar[] = "$";
    EXPECT_PRED_THROW(HierarchicalObjectName n("x$"),
                      std::invalid_argument, NameHasInvalidCharacter<dollar>);
}

bool NameHasUnbalancedBrackets(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
                      "Name has unbalanced brackets");
    return true;
}

bool NameHasNothingInBrackets(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
                      "Name has nothing in brackets");
    return true;
}

bool ArrayContentsMalformed(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
                      "Array contents are malformed");
    return true;
}

bool ArraySizeZero(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
                      "Dimension size is 0");
    return true;
}

bool checkZeroWidth(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Invalid width 0");
    return true;
}

TEST(TestHierarchicalObjectName, TestPublicMethods) {
    {
        HierarchicalObjectName n("x[");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, NameHasUnbalancedBrackets);
    }
    {
        HierarchicalObjectName n("x[2]]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, NameHasUnbalancedBrackets);
    }
    {
        HierarchicalObjectName n("x[[2]]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, NameHasUnbalancedBrackets);
    }
    {
        HierarchicalObjectName n("x[]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, NameHasNothingInBrackets);
    }
    {
        HierarchicalObjectName n("x[x]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArrayContentsMalformed);
    }
    {
        HierarchicalObjectName n("x[_2]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArrayContentsMalformed);
    }
    {
        HierarchicalObjectName n("x[2 32]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArrayContentsMalformed);
    }
    {
        HierarchicalObjectName n("x[2 stide 32]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArrayContentsMalformed);
    }
    {
        HierarchicalObjectName n("x[2stride 32]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArrayContentsMalformed);
    }
    {
        HierarchicalObjectName n("x[0]");
        EXPECT_PRED_THROW(n.arraySizesAndStrides(),
                          std::logic_error, ArraySizeZero);
    }
    {
        HierarchicalObjectName n {"x"};
        EXPECT_PRED_THROW(n.arrayNamesToOffsets(0),
                          std::invalid_argument, checkZeroWidth);
    }
    {
        HierarchicalObjectName n {"x"};
        EXPECT_EQ(n.base_name(), "x");
        EXPECT_TRUE(n.arraySizesAndStrides().empty());
        EXPECT_TRUE(n.arrayNamesToOffsets(2).empty());
        EXPECT_EQ(n.array_str(), "");
    }
    {
        HierarchicalObjectName n {"y2[2]"};
        EXPECT_EQ(n.base_name(), "y2");
        EXPECT_EQ(n.array_str(), "[2]");
        auto arraySizesAndStrides = n.arraySizesAndStrides();
        EXPECT_EQ(arraySizesAndStrides.size(), 1);
        auto &[dim, stride] = arraySizesAndStrides[0];
        EXPECT_EQ(dim, 2);
        EXPECT_EQ(stride, 0);
        auto arrayNamesToOffsets = n.arrayNamesToOffsets(2);
        EXPECT_EQ(arrayNamesToOffsets.size(), 2);
        int i = 0;
        for (auto &[name, offset] : arrayNamesToOffsets) {
            EXPECT_EQ(name, "y2[" + std::to_string(i) + "]");
            EXPECT_EQ(offset, i * 2);
            ++i;
        }
    }
    {
        HierarchicalObjectName n {"z2_3[2][3]"};
        EXPECT_EQ(n.base_name(), "z2_3");
        EXPECT_EQ(n.array_str(), "[2][3]");
        auto arraySizesAndStrides = n.arraySizesAndStrides();
        EXPECT_EQ(arraySizesAndStrides.size(), 2);
        auto &[dim0, stride0] = arraySizesAndStrides[0];
        EXPECT_EQ(dim0, 2);
        EXPECT_EQ(stride0, 0);
        auto &[dim1, stride1] = arraySizesAndStrides[1];
        EXPECT_EQ(dim1, 3);
        EXPECT_EQ(stride1, 0);
        auto arrayNamesToOffsets = n.arrayNamesToOffsets(4);
        EXPECT_EQ(arrayNamesToOffsets.size(), 2 * 3);
        int i = 0;
        for (auto &[name, offset] : arrayNamesToOffsets) {
            EXPECT_EQ(name, "z2_3[" + std::to_string(i / 3)     \
                      + "][" + std::to_string(i % 3) + "]");
            EXPECT_EQ(offset, i * 4);
            ++i;
        }
    }
    {
        HierarchicalObjectName n {"z[2 stride 16][3]"};
        EXPECT_EQ(n.base_name(), "z");
        EXPECT_EQ(n.array_str(), "[2 stride 16][3]");
        auto arraySizesAndStrides = n.arraySizesAndStrides();
        EXPECT_EQ(arraySizesAndStrides.size(), 2);
        auto &[dim0, stride0] = arraySizesAndStrides[0];
        EXPECT_EQ(dim0, 2);
        EXPECT_EQ(stride0, 16);
        auto &[dim1, stride1] = arraySizesAndStrides[1];
        EXPECT_EQ(dim1, 3);
        EXPECT_EQ(stride1, 0);
        auto arrayNamesToOffsets = n.arrayNamesToOffsets(1);
        EXPECT_EQ(arrayNamesToOffsets.size(), 2 * 3);
        int i = 0;
        for (auto &[name, offset] : arrayNamesToOffsets) {
            EXPECT_EQ(name, "z[" + std::to_string(i / 3)        \
                      + "][" + std::to_string(i % 3) + "]");
            EXPECT_EQ(offset, (i / 3) * 16 + (i % 3));
            ++i;
        }
    }
}
