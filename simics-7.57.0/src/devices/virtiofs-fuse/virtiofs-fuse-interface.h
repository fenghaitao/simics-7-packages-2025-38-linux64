/*
  virtiofs-fuse-interface.h - FUSE request handler interface

  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef VIRTIOFS_FUSE_INTERFACE_H
#define VIRTIOFS_FUSE_INTERFACE_H

#include <simics/device-api.h>

#if defined(__cplusplus)
extern "C" {
#endif

/* <add id="virtiofs_fuse_interface_t">

   This interface is intended for implementing a FUSE request handler.

   <fun>handle_request</fun> This method takes a FUSE request in <param>req
   </param>. It then returns a buffer_t object with the FUSE response. The
   caller of handle_request must free the data field in the returned buffer_t
   object.

   <insert-until text="// ADD INTERFACE virtiofs_fuse_interface"/>
   </add>

   <add id="virtiofs_fuse_interface_exec_context">
   Cell Context for all methods.
   </add>
*/

SIM_INTERFACE(virtiofs_fuse)
{
        buffer_t (*handle_request)(conf_object_t * obj, bytes_t req);
};

#define VIRTIOFS_FUSE_INTERFACE "virtiofs_fuse"
// ADD INTERFACE virtiofs_fuse_interface

#if defined(__cplusplus)
}
#endif

#endif /* ! VIRTIOFS_FUSE_INTERFACE_H */
