# © 2023 Intel Corporation

simics_add_module(empty-device-dml
  CLASSES empty_device_dml
  SOURCES empty-device-dml.dml module_load.py
  SIMICS_API 7
)
add_subdirectory(test)
