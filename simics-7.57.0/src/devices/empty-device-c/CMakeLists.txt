# © 2023 Intel Corporation

simics_add_module(empty-device-c
  CLASSES empty_device_c
  SOURCES empty-device-c.c module_load.py
  SIMICS_API 7
  INIT_LOCAL
)
add_subdirectory(test)
