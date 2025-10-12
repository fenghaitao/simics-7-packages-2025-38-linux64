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

simics_add_module(sample-device-c++
  CLASSES sample_device_cxx_after
          sample_device_cxx_after_bank
          sample_device_cxx_attribute_class_attribute
          sample_device_cxx_attribute_class_member_method
          sample_device_cxx_attribute_class_member_variable
          sample_device_cxx_attribute_custom_method
          sample_device_cxx_attribute_global_method
          sample_device_cxx_attribute_nested_stl_container
          sample_device_cxx_attribute_pseudo
          sample_device_cxx_attribute_specialized_converter
          sample_device_cxx_bank_by_code
          sample_device_cxx_bank_by_data
          sample_device_cxx_class_with_init_class
          sample_device_cxx_class_without_init_class
          sample_device_cxx_class_without_init_local
          sample_device_cxx_connect
          sample_device_cxx_connect_map_target
          sample_device_cxx_connect_to_descendant
          sample_device_cxx_event
          sample_device_cxx_interface
          sample_device_cxx_interface_c
          sample_device_cxx_interface_with_custom_info
          sample_device_cxx_logging
          sample_device_cxx_port_use_confobject
          sample_device_cxx_port_use_port
          sample_device_cxx_user_interface
  SOURCES sample-after.cc
          sample-after-bank.cc
          sample-attribute.cc
          sample-bank-by-code.cc
          sample-bank-by-data.cc
          sample-class.cc
          sample-connect.cc
          sample-event.cc
          sample-interface.cc
          sample-interface-c.cc
          sample-logging.cc
          sample-port.cc
          solve-methods-collision.cc
          init.c
          module_load.py
  INIT_LOCAL
)
simics_add_sanitizers(sample-device-c++)
target_link_libraries(sample-device-c++
  PRIVATE Simics::C++
  PRIVATE sample-interface::includes
)
# Set rpath to libstdc++
if(NOT WIN32)
  set_target_properties(sample-device-c++ PROPERTIES BUILD_RPATH $ORIGIN/../sys/lib)
endif()
add_subdirectory(test)
