# -*- Makefile ; coding: utf-8 -*-

# © 2010 Intel Corporation

# Simics module makefile

SIMICS_API := 7
MODULE_CLASSES = empty_device_python
THREAD_SAFE:=yes

PYTHON_FILES = empty_device_python.py module_load.py

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
