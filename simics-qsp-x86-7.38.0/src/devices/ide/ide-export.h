/*
  ide-export.h

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef __IDE_EXPORT_H__
#define __IDE_EXPORT_H__

#include <simics/device-api.h>

#if defined(__cplusplus)
extern "C" {
#endif

SIM_INTERFACE(ide_dma) {
        void (*init_dma)(conf_object_t *obj);
        void (*hard_reset)(conf_object_t *obj);
};

SIM_INTERFACE(ide_dma_v2) {
        void (*dma_ready)(conf_object_t *obj);
        void (*dma_not_ready)(conf_object_t *obj);
        void (*hard_reset)(conf_object_t *obj);
};

SIM_INTERFACE(bus_master_ide) {
        uint32 (*transfer_dma)(conf_object_t *obj, int channel, int drive, 
                               uint8 *buf, uint32 len);
        int (*interrupt)(conf_object_t *obj, int channel);
        int (*interrupt_clear)(conf_object_t *obj, int channel);
};

#if defined(__cplusplus)
}
#endif

#endif
