# -*- Makefile ; coding: utf-8 -*-

# © 2010 Intel Corporation

# Simics module makefile

# USER-TODO: specify the class(es) implemented in this module
MODULE_CLASSES=empty_device_c

# USER-TODO: set file-names
SRC_FILES = empty-device-c.c

PYTHON_FILES = module_load.py

MODULE_CFLAGS =

SIMICS_API := 7
THREAD_SAFE:=yes


ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
