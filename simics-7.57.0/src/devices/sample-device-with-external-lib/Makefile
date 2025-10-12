# -*- Makefile -*-

# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Simics module makefile


MODULE_CLASSES = sample_device_with_external_lib
SRC_FILES = sample-device-with-external-lib.dml
PYTHON_FILES = module_load.py
EXTRA_DIST_SRC_FILES = technically/arbitrary/path/on/disk/src/external_lib.c \
                       technically/arbitrary/path/on/disk/Makefile \
                       README.md

# The name of the library to link against without "lib" prefix and without OS
# specific extension
EXTERNAL_LIB_BASE_NAME := external_lib

# The external library could be anywhere on your disk we only have it in
#  $(SRC_BASE)/$(TARGET) because we want to make it available as part of the
#  device sources
EXTERNAL_LIB_LOC := $(SRC_BASE)/$(TARGET)/technically/arbitrary/path/on/disk

# COMPILE time settings. Tell the compiler where to find the headers and tell
# the linker where to find the library pass path to external lib and lib name
# to compiler/linker
MODULE_CFLAGS  += -I$(EXTERNAL_LIB_LOC)/include
MODULE_LDFLAGS += -L$(EXTERNAL_LIB_LOC)/lib
LIBS += -l$(EXTERNAL_LIB_BASE_NAME)

# As per documentation, add the rpath on Linux hosts. This is the RUNTIME
# setting. Tell the loader where to find the lib when running. We skip this for
# Windows as there is no RUNPATH on Windows. On Windows we depend on the
# project being associated with an add-on package that contains the
# win64/sys/lib folder with the external DLL we need. See README.md for more
# details.
ifeq ($(HOST_TYPE),linux64)
MODULE_LDFLAGS += -Wl,-rpath,'$$ORIGIN/../sys/lib'
endif

SIMICS_API := latest
THREAD_SAFE := yes

# Adjustments to support win64 and linux64
ifeq ($(HOST_TYPE),win64)
COPYCOMMAND := copy /Y
MKDIRCOMMAND := mkdir
EXTERNAL_LIB_FULL_NAME := lib$(EXTERNAL_LIB_BASE_NAME).dll
IS_WINDOWS=1
define path_fix
$(subst /,\,$1)
endef
else
COPYCOMMAND := cp
MKDIRCOMMAND := mkdir -p
EXTERNAL_LIB_FULL_NAME := lib$(EXTERNAL_LIB_BASE_NAME).so
IS_WINDOWS=0
define path_fix
$1
endef
endif

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif

# Add the copied lib as a prerequisite for the module
$(MODULE_SHLIB): $(TARGET_DIR)/../sys/lib/$(EXTERNAL_LIB_FULL_NAME)


# A simple copy rule to move the external lib into sys/lib. Now you could
# bundle the project into a package and it would be self-contained (i.e.,
# contain all libs needed to run. No external libs needed)
$(TARGET_DIR)/../sys/lib/$(EXTERNAL_LIB_FULL_NAME): $(EXTERNAL_LIB_LOC)/lib/$(EXTERNAL_LIB_FULL_NAME)
	@echo === Copying external lib ===
	-@$(MKDIRCOMMAND) $(call path_fix, $(TARGET_DIR)/../sys/lib)
	@$(COPYCOMMAND) $(call path_fix, $<)  $(call path_fix, $@)

# NOTE: In a real world situation the external lib would very likely be
# pre-built and the module makefile would not build it. But in order to CI test
# this module, we need to add the build dependency here
$(EXTERNAL_LIB_LOC)/lib/$(EXTERNAL_LIB_FULL_NAME):
	$(MAKE) -C $(EXTERNAL_LIB_LOC) IS_WINDOWS=$(IS_WINDOWS)
