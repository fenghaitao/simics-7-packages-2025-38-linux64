# -*- Makefile ; coding: utf-8 -*-

# © 2015 Intel Corporation

# Simics module makefile

MODULE_CLASSES := empty_device_pyobj

PYTHON_FILES = empty_device_pyobj.py module_load.py

THREAD_SAFE=yes
SIMICS_API := 7

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif

