# © 2023 Intel Corporation

simics_add_module(empty-device-pyobj
  CLASSES empty_device_pyobj
  SOURCES empty_device_pyobj.py module_load.py
  SIMICS_API 7
)
add_subdirectory(test)
