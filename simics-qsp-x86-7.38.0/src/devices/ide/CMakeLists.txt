# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# skip-cmake-conversion

# ide.cc is not currently distributed
if(SIMICS_REPO_ROOT)
  simics_add_module(ide
    CLASSES ide ide-disk ide-cdrom
    SOURCES ide.cc ide-array.c module_load.py
    INIT_LOCAL
    SIMICS_API latest
  )
  add_compile_definitions(DEVICE_IS_LITTLE_ENDIAN)
  add_subdirectory(test)

  add_library(ide-array INTERFACE)
  target_sources(ide-array INTERFACE ide-array.c)
  add_library(ide::ide-array ALIAS ide-array)
else()
  add_library(ide-imports INTERFACE)
  target_include_directories(ide-imports INTERFACE .)
  add_library(ide::imports ALIAS ide-imports)
  add_library(ide::includes ALIAS ide-imports)
endif()
