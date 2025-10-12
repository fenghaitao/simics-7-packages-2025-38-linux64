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

#ifndef CAN_INTERFACE_H
#define CAN_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
        Can_Status_No_Error = 0,
        Can_Status_Nack,
        Can_Status_Bit_Error,
        Can_Status_Stuff_Error,
        Can_Status_Crc_Error,
        Can_Status_Form_Error
} can_status_t;

#define CAN_DATA_MAX_NUM 8
 
/* <add-type id="can_frame_t">
   <ul> 
    <li><tt>Standard Format</tt>:<br/>
    Arbitration Field(11bit_ID+RTR)+Control Field(IDE+r0+DLC)
    </li>
    <li><tt>Extended Format</tt>:<br/>
    Arbitration Field(11bit_sID+SRR+IDE+18bit_eID+RTR)+Control Field(r1+r0+DLC)
    </li>
   </ul>
   Above are the Arbitration Field and Control Field of the physical Standard
   frame and Extended frame. But the <type>can_frame_t</type> only focus on the
   logical meanings of such fields and tries to adapt different CAN controllers:
   <ul>
     <li><tt>identifier</tt>: For Standard frame, 11bit_ID should be put in
     <tt>identifier[10:0]</tt>;for Extended frame, 11bit_sID should be put in 
     <tt>identifier[28:18]</tt> and 18bit_eID should be put in
     <tt>identifier[17:0]</tt>.</li>

     <li><tt>extended</tt>: There isn't IDE in can_frame_t, instead,
     <tt>extended</tt> is used to indicate if the frame is Extended frame or
     Standard frame.</li>

     <li><tt>rtr</tt>: There isn't SRR in can_frame_t for Extended frame,
     instead, <tt>rtr</tt> is used to indicate if the frame is a remote frame or
     not. Here we don't care whether the frame is Extended frame or Standard
     frame.</li>
     
     <li><tt>data_length</tt>: The <tt>data_length</tt> contains the arithmetic
     value of the DLC.</li>
     
     <li><tt>data[CAN_DATA_MAX_NUM]</tt>: This is the data field of Date frame.
     </li>
     
     <li><tt>crc</tt>: This is the crc field of a CAN frame.</li>
   </ul>
   </add-type>
*/

typedef struct {
        /* arbitration field */
        uint32 identifier;
        bool extended;
        bool rtr;
        /* control field */
        uint8 data_length;
        /* data field */
        uint8 data[CAN_DATA_MAX_NUM];
        /* crc field */
        uint16 crc;
} can_frame_t;

SIM_PY_ALLOCATABLE(can_frame_t);

/* <add id="can_device_interface_t">
   <insert-until text="// ADD INTERFACE can_device_interface"/>

   The <iface>can_device</iface> interface is implemented by CAN controllers.
   The <fun>receive</fun> function is called by can-endpoint to pass CAN frame
   from other can-endpoint to the connected CAN controller.

   The CAN frame is expressed by the <param>frame</param> parameter, which is a
   pointer of <type>can_frame_t</type>. The following is the details of 
   <type>can_frame_t</type>:

   <insert id="can_frame_t"/>

   </add>
   <add id="can_device_interface_exec_context">
   Cell Context for all methods.
   </add>
*/

SIM_INTERFACE(can_device) {
        void (*receive)(conf_object_t *obj, can_frame_t *frame);
};
#define CAN_DEVICE_INTERFACE "can_device"
// ADD INTERFACE can_device_interface

/* <add id="can_link_interface_t">
   <insert-until text="// ADD INTERFACE can_link_interface"/>

   The <iface>can_link</iface> interface is implemented by can-endpoint.
   The <fun>send</fun> function is called by CAN controller to pass CAN frame
   to the connected can-endpoint. Then can-link delivers the CAN frame to other
   can-endpoints.

   </add>
   <add id="can_link_interface_exec_context">
   Cell Context for all methods.
   </add>
*/

SIM_INTERFACE(can_link) {
        can_status_t (*send)(conf_object_t *obj, can_frame_t *frame);
};
#define CAN_LINK_INTERFACE "can_link"
// ADD INTERFACE can_link_interface

#ifdef __cplusplus
}
#endif

#endif /* ! CAN_INTERFACE_H */
