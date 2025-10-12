/*
  © 2015 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef GENERIC_MESSAGE_INTERFACES_H
#define GENERIC_MESSAGE_INTERFACES_H

#include <simics/base/types.h>
#include <simics/base/time.h>
#include <simics/util/dbuffer.h>
#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/* <add id="generic_message_link_interface_t">
   <insert-until text="// ADD INTERFACE generic_message_link_interface"/>

   <note>This interface is used for gml-link which is based on the link library.
    Refer to the <cite>Link Library</cite> for more information.</note>

   This interface is implemented by generic message link objects that provide a
   data link layer interface for frame delivery. It is used by the device
   object to talk to the link object. The device must implement the
   <iface>generic_message_device</iface> interface.

   The <fun>connect_device</fun> function attaches a generic link device to the
   link. The return value is an identification number that should be used
   in subsequent calls to the link to identify the device. The
   <param>address</param> parameter sets the address of the device on the link.
   Currently the <param>new_connection</param> parameter is not in use, a NULL
   pointer can be passed as the parameter.

   The <fun>disconnect_device</fun> function detaches a generic link
   device from the link.  It will not receive any more frames from the
   link and may not call any functions in the interface, except
   <fun>connect_device</fun>.

   The <fun>send_frame</fun> function is used by a device to send a generic
   device frame onto the link to be delivered to another device connected to
   the same link.  The frame should be a <type><idx>dbuffer_t</idx></type>
   containing a data frame.  The <param>address</param> parameter is the address
   to sent the frame to. The <param>delay</param> makes it possible to add a
   small delay to the frame.  This can be used when a device wants to send
   multiple frames at once, but want them to be delivered in a specific
   sequence.  Instead of using an event handler to send each frame, they can be
   sent at once, with an increasing delay for each frame. The delay is given in
   nanoseconds.

   </add>
   <add id="generic_message_link_interface_exec_context">
   <table border="false">
   <tr><td><fun>connect_device</fun></td><td>Global Context</td></tr>
   <tr><td><fun>disconnect_device</fun></td><td>Global Context</td></tr>
   <tr><td><fun>send_frame</fun></td><td>Cell Context</td></tr>
   </table>
   </add>
 */
SIM_INTERFACE(generic_message_link) {
#ifndef PYWRAP
        int  (*connect_device)(conf_object_t *_obj, conf_object_t *dev,
                               int *new_connection, uint32 address);
        void (*disconnect_device)(conf_object_t *_obj, conf_object_t *dev);
#endif
        void (*send_frame)(conf_object_t *_obj, int id, uint32 address,
                           dbuffer_t *frame, nano_secs_t delay);
};

#define GENERIC_MESSAGE_LINK_INTERFACE "generic_message_link"
// ADD INTERFACE generic_message_link_interface

/* <add id="generic_message_device_interface_t">
   <insert-until text="// ADD INTERFACE generic_message_device_interface"/>

   This interface is implemented by generic message device objects that connect
   to <class>generic-message-link</class> objects.  It is used by the link
   object to send messages to the device object. The link should implement the
   <iface>generic_message_link</iface> interface.

   The <fun>receive_frame</fun> function is called by the link to send a frame
   to the device.  The frame is passed as a <type><idx>dbuffer_t</idx></type>
   pointer that may not be modified without cloning it first.

   </add>
   <add id="generic_message_device_interface_exec_context">
   <table border="false">
   <tr><td><fun>receive_frame</fun></td><td>Cell Context</td></tr>
   </table>
   </add>

   </add>
*/
SIM_INTERFACE(generic_message_device) {
        void (*receive_frame)(conf_object_t *dev, conf_object_t *link,
                              dbuffer_t *frame);
};

#define GENERIC_MESSAGE_DEVICE_INTERFACE "generic_message_device"
// ADD INTERFACE generic_message_device_interface

#ifdef __cplusplus
}
#endif

#endif /* ! GENERIC_MESSAGE_INTERFACES_H */
