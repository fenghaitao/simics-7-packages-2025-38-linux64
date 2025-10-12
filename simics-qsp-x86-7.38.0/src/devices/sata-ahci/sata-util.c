/*
  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "sata-util.h"

const char *
sata_fis_type_name(int type)
{
    switch (type) {
    case FIS_REG_H2D:
        return "FIS_REG_H2D";
    case FIS_REG_D2H:
        return "FIS_REG_D2H";
    case FIS_DMA_ACTIVATE_D2H:
        return "FIS_DMA_ACTIVATE_D2H";
    case FIS_DMA_SETUP_BI:
        return "FIS_DMA_SETUP_BI";
    case FIS_DATA_BI:
        return "FIS_DATA_BI";
    case FIS_BIST_ACTIVATE_BI:
        return "FIS_BIST_ACTIVATE_BI";
    case FIS_PIO_SETUP_D2H:
        return "FIS_PIO_SETUP_D2H";
    case FIS_SET_DEVICE_BIT_D2H:
        return "FIS_SET_DEVICE_BIT_D2H";
    }

    return "FIS_UNRECOGNIZED";
}
