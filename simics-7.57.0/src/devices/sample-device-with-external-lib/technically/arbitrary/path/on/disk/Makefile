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

# Simple makefile for a trivial Simics-external library


# Assumption is that $(CC) points to a working GNU compiler
#  could be mingw64 on Windows
# Make needs to be invoked with IS_WINDOWS either 0 or 1

ifeq ($(IS_WINDOWS),)
  $(error Please set IS_WINDOWS to either 0 or 1)
endif

ifeq ($(IS_WINDOWS),1)
  $(warning Assuming Windows host)
  HOST:=win64
  RMCMD=del
  define path_fix
    $(subst /,\,$1)
  endef
else
  $(warning Assuming Linux host)
  HOST:=linux64
  RMCMD=rm -f
  define path_fix
    $1
  endef
endif

INCLUDE=-Iinclude

SRC = external_lib.c

ifeq ($(IS_WINDOWS),1)
OBJEXT = dll
else
OBJEXT = so
endif

LIB = lib/$(patsubst %.c,lib%.$(OBJEXT),$(SRC))

.PHONY: all

all: $(LIB)

clean:
	$(RMCMD) $(call path_fix,$(LIB))

lib/lib%.$(OBJEXT): src/%.c
	-@mkdir lib
	$(CC) $(INCLUDE) -fPIC -shared -o $@ $< -Wl,--soname=$(patsubst %.c,lib%.$(OBJEXT),$(SRC))
