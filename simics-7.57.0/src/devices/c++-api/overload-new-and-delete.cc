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

// SIMICS-21235 std::string constructor may be inlined and bypassing the
// overloaded new. Use it only in the DEBUG build
#ifndef NDEBUG

#include <simics/util/alloc.h>

#include <cstddef>
#include <cstdio>
#include <new>  // bad_alloc

void *operator new(std::size_t size) {
    void *addr = mm_zalloc(size, size, "C++ new was invoked here",
                           __FILE__, __LINE__);
    if (addr == nullptr) {
        throw std::bad_alloc();
    }
    return addr;
}

void *operator new[](std::size_t size) {
    return ::operator new(size);
}

void operator delete(void *addr) noexcept {
    MM_FREE(addr);
}

void operator delete[](void *addr) noexcept {
    return ::operator delete(addr);
}

// Per C++ standard 18.6.1.1, if operator delete function wo size is defined,
// it should also define the following function
void operator delete(void *addr, std::size_t size) noexcept {
    ::operator delete(addr);
}

void operator delete[](void *addr, std::size_t size) noexcept {
    ::operator delete[](addr);
}

#endif
