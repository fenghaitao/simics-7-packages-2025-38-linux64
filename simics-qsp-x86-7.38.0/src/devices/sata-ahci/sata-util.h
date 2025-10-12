/*
  © 2011 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SATA_UTIL_H
#define SATA_UTIL_H

#include <simics/device-api.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EXT_ADDR(low, ext, support_64) (support_64 ? (((physical_address_t)(ext) << 32) | (low)) : low)

enum {
        FIS_REG_H2D             = 0x27,
        FIS_REG_D2H             = 0x34,
        FIS_DMA_ACTIVATE_D2H    = 0x39,
        FIS_DMA_SETUP_BI        = 0x41, //'BI': bi-direction
        FIS_DATA_BI             = 0x46,
        FIS_BIST_ACTIVATE_BI    = 0x58,
        FIS_PIO_SETUP_D2H       = 0x5F,
        FIS_SET_DEVICE_BIT_D2H  = 0xA1,
        FIS_COMINIT             = 0xFE, // Fake FIS to simulate COMINIT
};

const char * sata_fis_type_name(int type);

#ifdef __cplusplus
}
#endif

#endif // SATA_UTIL_H
