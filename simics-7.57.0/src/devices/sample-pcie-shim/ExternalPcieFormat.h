/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SAMPLE_PCIE_SHIM_EXTERNALPCIEFORMAT_H
#define SAMPLE_PCIE_SHIM_EXTERNALPCIEFORMAT_H

#include <cstdint>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#pragma pack(push, 1)

typedef enum {
    PCIE_TLP_TYPE_NOT_SET = 0,
    PCIE_TLP_TYPE_MSG = 1,
    PCIE_TLP_TYPE_CFG = 2,
    PCIE_TLP_TYPE_MEM = 3,
    PCIE_TLP_TYPE_IO = 4,
} pcie_tlp_type_t;

struct pcie_tlp_header {
    uint64_t addr;
    uint8_t type;
};

struct pcie_tlp_msg_header {
    uint16_t destination_id;
    uint8_t msg_type;
    uint8_t route;
    uint16_t payload_len;
};

struct pcie_tlp_cfg_header {
    uint16_t bdf;
    uint16_t ofs;
    uint16_t payload_len;
    uint8_t rnw;
    uint8_t type0;
};

struct pcie_tlp_mem_header {
    uint64_t len;
    uint8_t rnw;
};

struct pcie_tlp_io_header {
    uint64_t len;
    uint8_t rnw;
};

struct external_request {
    struct pcie_tlp_header pcie_hdr;
};

typedef enum {
    EXTERNAL_RESPONSE_TYPE_SUCCESS = 0,
    EXTERNAL_RESPONSE_TYPE_ERROR = 1,
} external_response_result_t;

struct external_response {
    uint64_t payload_len;
    uint8_t ret;
};

typedef enum {
    EXTERNAL_TYPE_REQUEST = 0xEF,
    EXTERNAL_TYPE_RESPONSE = 0xAB,
} packet_type_t;

struct external_packet {
    uint8_t type;
    uint64_t tag;
    uint32_t packet_len;
};

#pragma pack(pop)

#if defined(__cplusplus)
}
#endif

#endif  // SAMPLE_PCIE_SHIM_EXTERNALPCIEFORMAT_H
