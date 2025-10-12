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

simics_add_module(p-display
  CLASSES p_display
  SOURCES p-display.dml manage-png-images.c module_load.py
  INIT_LOCAL
  SIMICS_API 6
)

target_link_libraries(p-display
  PRIVATE p-display-draw-interface::imports
)

# To build p-display we need ZLIB and PNG; but we don't care if either is
# missing. This allows end-users to configure this module on a system without
# ZLIB and PNG.
set(IGNORE_MISSING_LIBS True)

simics_add_external_build_dependency(p-display ZLIB)
if(NOT ZLIB_FOUND)
  message(WARNING "p-display needs ZLIB; please provide ZLIB_ROOT or install ZLIB")
endif()

simics_add_external_build_dependency(p-display PNG)
if(NOT PNG_FOUND)
  message(WARNING "p-display needs PNG; please provide PNG_ROOT or install PNG")
endif()

add_subdirectory(test)

if(NOT TARGET all-training-modules)
  add_custom_target(all-training-modules)
endif()

add_dependencies(all-training-modules p-display)

