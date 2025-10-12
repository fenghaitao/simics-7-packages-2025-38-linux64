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

MODULE_CLASSES = p_display
SRC_FILES = p-display.dml  manage-png-images.c
PYTHON_FILES = module_load.py

SIMICS_API := 6
THREAD_SAFE := yes

DMLC_FLAGS = 

# Add references to custom interface for drawing
EXTRA_MODULE_VPATH += p-display-draw-interface

# Locating the PNG headers and library
#
# When building in core, just use the predefined variables
#
# When in a project, settings will have to be adjusted to account
# for the setup of the local machine.  
# 

ifeq ($(SIMICS_CORE),)

ifeq ($(HOST_TYPE),linux64)
$(info In project on Linux, setting up to find PNG)
#   No need to set the include dir, in case libpng is installed as 
#   part of the standard libraries on the host
# PNG_INCLUDE_DIR 
LIBPNG = -lpng     # Will find the PNG lib in Simics at runtime
endif

ifeq ($(HOST_TYPE),win64)
$(info In project on Windows, setting up to find PNG)
#    You need to install a mingw64 libpng library
#    and point at its location here, for headers
#    And point at the DLL in Simics base to make linking
#    work correctly. 
PNG_INCLUDE_DIR = C:\mingw64\libpng-1.6.37-mingw64\include
LIBPNG = $(SIMICS_BASE)/$(HOST_TYPE)/bin/libpng16-16.dll
endif

endif

# These lines work in the Simics core build, as well as in a
# project build if the two variables have been defined above
MODULE_CFLAGS += -I$(PNG_INCLUDE_DIR) 
MODULE_LDFLAGS = $(LIBZ) $(LIBPNG)

COMPILE_PYC = 0

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
