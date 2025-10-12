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

#ifndef SIMICS_BANK_ISSUE_CALLBACKS_INTERFACE_H
#define SIMICS_BANK_ISSUE_CALLBACKS_INTERFACE_H

namespace simics {

class BankAccess;

enum class CallbackType : int { AR = 1, AW, BR, BW };

class BankIssueCallbacksInterface {
  public:
    virtual ~BankIssueCallbacksInterface() = default;

    virtual void issue_callbacks(BankAccess *handle,
                                 CallbackType type) const = 0;
};

}  // namespace simics

#endif
