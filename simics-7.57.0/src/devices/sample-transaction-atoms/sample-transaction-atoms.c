/*
  sample-transaction-atoms.h - sample definition of new transaction atoms

  © 2020 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

/* This module is an example of defining new transaction atoms. See the
   "Custom Atom Types" section of the
   "Simics Model Builder User's Guide" for further documentation.
*/


#include <simics/simulator-api.h>  // for SIM_printf
static void function_with_sample_code();

/* The following comment is here just to incorporate this code sample
   into Simics documentation. The comment can be safely removed. */
//:: pre doc-custom-atom-types-2 {{
#include "sample-transaction-atoms.h"

void
init_local()
{
        ATOM_register_device_address();
        ATOM_register_complex();

        // function_with_sample_code contains sample code showing how
        // to create transactions and access the new atoms we just defined.
        function_with_sample_code();
}
// }}


/* Function with some sample code. */
static void
function_with_sample_code()
{
        // Sample code showing how to create a 1 byte read transaction
        // with device_address and complex atoms:
        uint8 val;
        complex_atom_t complex_atom = {
                .address = 0x8086,
                .attributes = 0,
        };
        atom_t atoms[] = {
                ATOM_flags(0),
                ATOM_data(&val),
                ATOM_size(sizeof val),
                ATOM_device_address(0x8086),
                ATOM_complex(&complex_atom),
                ATOM_LIST_END
        };
        transaction_t t = { atoms };

        // Sample code showing how to get device_address and complex atoms
        // from a transaction:
        uint64 device_address = ATOM_get_transaction_device_address(&t);
        complex_atom_t *complex = ATOM_get_transaction_complex(&t);


        SIM_printf("Device address: %#llx\n", device_address);
        SIM_printf("complex.address: %#llx\n", complex->address);
        SIM_printf("complex.attributes: %#x\n", complex->attributes);

/* The following comment is here just to incorporate the following code
   sample into Simics documentation. It can be safely removed. */
//:: pre doc-custom-atom-types-4 {{
        const uint64 *dev_address = ATOM_transaction_device_address(&t);
        if (dev_address != NULL) {
                // atom is present, pointer is valid
                SIM_printf("Device address: %#llx\n", *dev_address);
        } else {
                // atom is not present
                SIM_printf("Device address atom is not present\n");
        }
// }}
}
