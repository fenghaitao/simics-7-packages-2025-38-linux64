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


# Try to set up all the flashes listed in flash_memory.py

SIM_source_python_in_module("common.py", __name__)

# 28F___C3_
make_flash_configuration("28F800C3B", 1, 16, "flash0000")
make_flash_configuration("28F160C3B", 1, 16, "flash0001")
make_flash_configuration("28F320C3B", 1, 16, "flash0002")
make_flash_configuration("28F640C3B", 1, 16, "flash0003")
make_flash_configuration("28F800C3T", 1, 16, "flash0004")
make_flash_configuration("28F160C3T", 1, 16, "flash0005")
make_flash_configuration("28F320C3T", 1, 16, "flash0006")
make_flash_configuration("28F640C3T", 1, 16, "flash0007")

# 28F___J3A
make_flash_configuration("28F128J3A", 1, 16, "flash0100")
make_flash_configuration("28F320J3A", 1, 16, "flash0101")
make_flash_configuration("28F640J3A", 1, 16, "flash0102")

# 28F___J3
make_flash_configuration("28F128J3", 1, 16, "flash0200")
make_flash_configuration("28F320J3", 1, 16, "flash0201")
make_flash_configuration("28F640J3", 1, 16, "flash0202")
make_flash_configuration("28F256J3", 1, 16, "flash0203")

# Am29F040B
make_flash_configuration("Am29F040B", 1, 8, "flash0300")

# Am29F016D
make_flash_configuration("Am29F016D", 1, 8, "flash0400")

# Am29SL160CT
make_flash_configuration("Am29SL160CT", 1, 16, "flash0500")

# Am29LV640MH
make_flash_configuration("Am29LV640MH", 1, 16, "flash0600")

# SG29GL064M
make_flash_configuration("SG29GL064M", 1, 16, "flash0700")

# Am29LV160MB
make_flash_configuration("Am29LV160MB", 1, 16, "flash0800")

# SG29GL064M
make_flash_configuration("S29GL064A", 1, 16, "flash0900")

make_flash_configuration("SST39VF040", 1, 8, "flash1000")

run_command("list-objects")
