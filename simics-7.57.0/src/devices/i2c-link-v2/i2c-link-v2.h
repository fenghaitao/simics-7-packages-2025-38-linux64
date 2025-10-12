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

#include <string.h>
#include <simics/devs/liblink.h>
#include <simics/devs/i2c.h>

typedef enum {
        start_request = 0,
        start_response = 1,
        read_request = 2,
        read_response = 3,
        write_request = 6,
        write_response = 7,
        stop = 8,
        start_response_pending = 9
} i2c_link_action_type_t;

typedef enum {
        state_idle = 0,
        state_wait_rsp_start_r = 1,
        state_wait_rsp_start_w = 2,
        state_wait_req_r = 3,
        state_wait_req_w = 4,
        state_wait_rsp_r = 5,
        state_wait_rsp_w = 6,
        state_wait_stop = 10,
        state_wait_remote_master = 11,
        state_wait_remote_start_rsp = 12,
        state_wait_rsp_10bit_addr_w = 13
} i2c_link_state_t;

#define MAX_ADDRESSES 128
#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

/* Return the name of the message type */
static inline const char *
i2c_type_name(i2c_link_action_type_t type)
{
        switch(type) {
        case start_request:
                return "start request";
        case start_response:
                return "start response";
        case read_request:
                return "read request";
        case read_response:
                return "read response";
        case write_request:
                return "write request";
        case write_response:
                return "write response";
        case stop:
                return "stop";
        case start_response_pending:
                return "start response pending";
        }
        return "unknown type";
}
