// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2016 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_MALLOC_ALLOCATOR_H
#define SIMICS_MALLOC_ALLOCATOR_H

#include <simics/util/alloc.h>
#include <stddef.h>

#include <new>
#include <memory>

namespace simics {

template <class T>
class MmAllocator {
  public:
    static void *allocate(std::size_t num) {
        return MM_MALLOC(num, T);
    }

    static void deallocate(T * const addr) {
        MM_FREE(addr);
    }
};

template <class T, template <class> class Allocator = MmAllocator>
class MallocAllocator {
  public:
    virtual T *allocate(const size_t num_elements) const {
        if (num_elements == 0) {
            return nullptr;
        }
        if (num_elements > max_size()) {
            throw std::bad_alloc();
        }

        void *addr = Allocator<T>::allocate(num_elements);
        if (!addr) {
            throw std::bad_alloc();
        }
        return static_cast<T*>(addr);
    }

    T *allocate(const size_t num_elements,
                std::allocator_traits<std::allocator<void> >
                    ::const_pointer hint) const {
        return allocate(num_elements);
    }

    void deallocate(T * const addr, const size_t n) const {
        Allocator<T>::deallocate(addr);
    }

    void construct(T * const uninitialized, const T &val) const {
        void * const initialized = static_cast<void*>(uninitialized);
        new(initialized) T(val);
    }
    void destroy(T * const p) const {
        p->~T();
    }

    // Returns the maximum number of elements that may be allocated
    size_t max_size() const {
        return static_cast<size_t>(-1) / sizeof(T);
    }

    T *address(T &x) const {  // NOLINT (runtime/references)
        return &x;
    }
    const T *address(const T &x) const {
        return &x;
    }

    // Always returns true since the allocator is stateless. Any memory
    // allocated using this allocator may be freed by another allocator
    bool operator==(const MallocAllocator &other) const {
        return true;
    }
    bool operator!=(const MallocAllocator &other) const {
        return !(*this == other);
    }

    MallocAllocator() {}
    MallocAllocator(const MallocAllocator&) {}
    ~MallocAllocator() {}

    template <typename U>
    MallocAllocator(const MallocAllocator<U, Allocator> &) {}

    MallocAllocator &operator=(const MallocAllocator &other) const {
        return this;
    }

    // Member type definitions required for all allocators:
    typedef T *pointer;
    typedef const T *const_pointer;

    typedef T &reference;
    typedef const T &const_reference;

    typedef T value_type;
    typedef size_t size_type;
    typedef ptrdiff_t difference_type;

    template <typename U> struct rebind {
        typedef MallocAllocator<U, Allocator> other;
    };
};

}  // namespace simics

#endif
