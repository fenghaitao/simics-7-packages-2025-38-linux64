# © 2023 Intel Corporation

simics_add_module(empty-device-python
  CLASSES empty_device_python
  SOURCES empty_device_python.py module_load.py
  SIMICS_API 7
)
add_subdirectory(test)
