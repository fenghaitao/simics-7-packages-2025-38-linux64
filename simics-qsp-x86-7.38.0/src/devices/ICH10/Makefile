# -*- Makefile -*-

# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

DEVICES = lpc \
          sata_f2 \
          sata_f5 \
          thermal \
          smbus \
          smbus_i2c_v2 \
          usb_uhci \
          usb_ehci \
          bridge \
          hpe_timer \
          timer \
          rtc \
          spi \
          cf9

MODULE_CLASSES := $(addprefix ich10_, $(DEVICES))

SRC_FILES = empty-init-local.c sata-util.c \
            $(addsuffix .dml, $(subst _,-,$(DEVICES)))

MODULE_CFLAGS =

EXTRA_MODULE_VPATH += ICH:ICH/lpc:ICH/sata
EXTRA_MODULE_VPATH += io-apic:ide::serial-interrupt-interface:sata-ahci:dml-lib

PYTHON_FILES := module_load.py ich_commands.py

THREAD_SAFE = yes
SIMICS_API = 6


include $(MODULE_MAKEFILE)
