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

/* The folling comment is here just to incorporate this code sample
   into Simics documentation. The comment can be safely removed. */
//:: pre doc-custom-atom-types-1 {{
#ifndef SAMPLE_TRANSACTION_ATOMS_H
#define SAMPLE_TRANSACTION_ATOMS_H
#include <simics/device-api.h>

#if defined(__cplusplus)
extern "C" {
#endif

// Define the 'device_address' atom type
#define ATOM_TYPE_device_address uint64
SIM_CUSTOM_ATOM(device_address);

// Define the 'complex' atom type
typedef struct {
        uint64 address;
        uint32 attributes;
} complex_atom_t;

// Allow creation from Python, if required
SIM_PY_ALLOCATABLE(complex_atom_t);
#define ATOM_TYPE_complex complex_atom_t *
SIM_CUSTOM_ATOM(complex);

#if defined(__cplusplus)
}
#endif

#endif /* SAMPLE_TRANSACTION_ATOMS_H */
// }}
