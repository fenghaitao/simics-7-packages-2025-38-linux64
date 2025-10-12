/*
  firewire-bus.c - FireWire bus

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>
#include <simics/devs/firewire.h>

hap_type_t hap_transfer;
hap_type_t hap_reset;

void
init_local()
{
        hap_transfer = SIM_hap_add_type("Firewire_Transfer",
                                     "", NULL, NULL,
                                     "Triggered when an packet travels"
                                     " through a firewire bus. During the hap"
                                     " handler the current_transfer"
                                     " attribute of the bus can be used to"
                                     " inspect and/or change the current"
                                     " transfer. If you set it to NULL the"
                                     " transfer is aborted and"
                                     " Firewire_V2_Ack_No_Ack is returned to"
                                     " the initiator of the transfer.", 0);
        hap_reset = SIM_hap_add_type("Firewire_Reset", "", NULL, NULL,
                                     "Triggered when the bus is reset."
                                     " It is invoked after calculating the"
                                     " default topology. During the hap the"
                                     " self_ids attribute can be used to"
                                     " change the self id packets sent to the"
                                     " devices on the bus. The"
                                     " connected_devices attribute can also be"
                                     " changed to modify the mapping from"
                                     " physical id to device.", 0);
}
