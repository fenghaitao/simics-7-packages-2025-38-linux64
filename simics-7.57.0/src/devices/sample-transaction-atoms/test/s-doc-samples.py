# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# The following code is not really a test but just sample code
# from Simics documentation.

#:: pre doc-custom-atom-types-3 {{
from simics import (
    SIM_load_module,
    transaction_t,
)

# Load the module defining custom transaction atoms:
SIM_load_module('sample-transaction-atoms')
# Import the complex_atom_t type from the custom_transaction_atoms module:
from simmod.sample_transaction_atoms.sample_transaction_atoms import (
    complex_atom_t,
)


# Transaction with the device_address atom
t1 = transaction_t(write=True, size=8, device_address=0x7)
print(f"Device address: {t1.device_address:#x}")

# Transaction with the complex atom
t2 = transaction_t(
    complex=complex_atom_t(address=0x10, attributes=0x5))
print(f"complex.address: {t2.complex.address:#x}")
print(f"complex.attributes: {t2.complex.attributes:#x}")
# }}
