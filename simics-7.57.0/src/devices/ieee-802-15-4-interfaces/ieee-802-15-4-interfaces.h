/*
 * ieee-802-15-4-interfaces.h

  © 2014 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef IEEE_802_15_4_INTERFACES_H
#define IEEE_802_15_4_INTERFACES_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/*

   Interfaces for IEEE 802.15.4
   --------------------------------

   Interfaces of IEEE 802.15.4 aim at creating a Simics model to simulate
   the data transmission service of IEEE 802.15.4 physical layers.
   The use should be analogous to Simics Ethernet Links, as far as possible
   given the somewhat dissimilar properties of wired switched networks
   and broadcast radio networks.

*/

/* <add-type id="ieee_802_15_4_frame_crc_status_t">
   <ul>
     <li><tt>IEEE_802_15_4_Frame_CRC_Match</tt> means that to the link that,
     regardless of the actual contents of the CRC field in frame, the CRC is
     considered matching the frame contents.</li>

     <li><tt>IEEE_802_15_4_Frame_CRC_Mismatch</tt> means that the CRC field
     and the frame contents do not agree. Just like the Ethernet links, the
     endpoint does not really send out the packet in this case.</li>

     <li><tt>IEEE_802_15_4_Frame_CRC16_Unknown/IEEE_802_15_4_Frame_CRC32_Unknown
     </tt> means that the link to compute the CRC and compare it with
     FCS (Frame Check Sequence) of the MAC frame. If the CRC field and frame
     contents do not agree, the endpoint does not send out the packet.
     <tt>IEEE_802_15_4_Frame_CRC32_Unknown</tt> is for 802.15.4g only.</li>
   </ul>
   </add-type> */
typedef enum {
        IEEE_802_15_4_Frame_CRC_Match = 0,
        IEEE_802_15_4_Frame_CRC_Mismatch,
        IEEE_802_15_4_Frame_CRC16_Unknown,
        IEEE_802_15_4_Frame_CRC32_Unknown,
} ieee_802_15_4_frame_crc_status_t;

/* <add-type id="ieee_802_15_4_transmit_status_t">
   <ul>
     <li><tt>IEEE_802_15_4_Transmit_No_Error</tt> means that the frame was
     sent out without error.</li>

     <li><tt>IEEE_802_15_4_Transmit_Channel_Contention</tt> means that there
     was collision and the frame was not sent out.</li>

     <li><tt>IEEE_802_15_4_Transmit_Data_Corruption</tt> means that the
     endpoint detected CRC mismatch and didn't send out the frame.</li>
   </ul>
   </add-type> */
typedef enum {
        IEEE_802_15_4_Transmit_No_Error = 0,
        IEEE_802_15_4_Transmit_Channel_Contention,
        IEEE_802_15_4_Transmit_Data_Corruption
} ieee_802_15_4_transmit_status_t;

/* <add-type id="ieee_802_15_4_probe_side_t">
   <ul>
     <li><tt>IEEE_802_15_4_Probe_Port_A</tt> means that the frame is
     from device to link.</li>

     <li><tt>IEEE_802_15_4_Probe_Port_B</tt> means that the frame is
     from link to device.</li>
   </ul>
   </add-type> */
typedef enum {
        IEEE_802_15_4_Probe_Port_A = 0,
        IEEE_802_15_4_Probe_Port_B = 1
} ieee_802_15_4_probe_side_t;

/* <add id="ieee_802_15_4_link_interface_t">
   <insert-until text="// ADD INTERFACE ieee_802_15_4_link_interface"/>

   The <iface>ieee_802_15_4_link</iface> interface is implemented by the IEEE
   802.15.4 link endpoint objects that provide an interface for frame traffic.

   Transceiver calls <fun>transmit</fun> to send out frames. The return value
   is using one of the values in the
   <type>ieee_802_15_4_transmit_status_t</type> enum:

   <insert id="ieee_802_15_4_transmit_status_t"/>

   The <param>crc_status</param> parameter provides out-of-band information on
   the contents of the frame with regards to the CRC field using one of the
   values in the <type>ieee_802_15_4_frame_crc_status_t</type> enum:

   <insert id="ieee_802_15_4_frame_crc_status_t"/>

   The frequency channels are defined through a combination of channel numbers
   and channel pages. Channel page is a concept added to IEEE 802.15.4 in 2006
   to distinguish between supported PHYs. Both channel page and channel number
   must match on source and target sides for successful transmission.

   </add>
   <add id="ieee_802_15_4_link_interface_exec_context">
   Cell Context for all methods.
   </add>
*/
SIM_INTERFACE(ieee_802_15_4_link) {
        ieee_802_15_4_transmit_status_t (*transmit)(
                                conf_object_t *NOTNULL obj,
                                const frags_t *frame,
                                uint16 channel_page,
                                uint16 channel_number,
                                ieee_802_15_4_frame_crc_status_t crc_status);
};
#define IEEE_802_15_4_LINK_INTERFACE "ieee_802_15_4_link"
// ADD INTERFACE ieee_802_15_4_link_interface

/* <add id="ieee_802_15_4_control_interface_t">
   <insert-until text="// ADD INTERFACE ieee_802_15_4_control_interface"/>

   The <iface>ieee_802_15_4_control</iface> interface is implemented by the
   IEEE 802.15.4 link endpoint objects that provide a interface for endpoint
   configuration. Simics command (Python program) calls <fun>set_rssi</fun>,
   <fun>remove_rssi</fun> and <fun>clear_all_rssi</fun> to update
   the RSSI table.

   </add>
   <add id="ieee_802_15_4_control_interface_exec_context">
   Cell Context for all methods.
   </add>
*/
SIM_INTERFACE(ieee_802_15_4_control) {
        void (*set_rssi)(conf_object_t *NOTNULL obj,
                         uint64 tgt_ep_id,
                         uint32 rssi);
        void (*remove_rssi)(conf_object_t *NOTNULL obj,
                            uint64 tgt_ep_id);
        void (*clear_all_rssi)(conf_object_t *NOTNULL obj);
};
#define IEEE_802_15_4_CONTROL_INTERFACE "ieee_802_15_4_control"
// ADD INTERFACE ieee_802_15_4_control_interface

/* <add id="ieee_802_15_4_receiver_interface_t">
   <insert-until text="// ADD INTERFACE ieee_802_15_4_receiver_interface"/>

   The <iface>ieee_802_15_4_receiver</iface> interface is implemented by the
   IEEE 802.15.4 transceivers that provide an interface for traffic.
   Endpoints call <fun>receive</fun> to deliver a frame to transceiver.
   Transceiver should check if the received frame from endpoint is in the
   channel that it is using. The channel being used is defined by channel_page
   and channel_number.
   Endpoints call <fun>frame_lost</fun> to notify transceivers on that a frame
   was lost because of low RSSI value.

   </add>
   <add id="ieee_802_15_4_receiver_interface_exec_context">
   Cell Context for all methods.
   </add>
*/
SIM_INTERFACE(ieee_802_15_4_receiver) {
        void (*receive)(conf_object_t *NOTNULL obj,
                        const frags_t *frame,
                        uint32 rssi,
                        uint16 channel_page,
                        uint16 channel_number,
                        ieee_802_15_4_frame_crc_status_t crc_status);
        void (*frame_lost)(conf_object_t *NOTNULL obj,
                           uint32 rssi,
                           uint16 channel_page,
                           uint16 channel_number);
};
#define IEEE_802_15_4_RECEIVER_INTERFACE "ieee_802_15_4_receiver"
// ADD INTERFACE ieee_802_15_4_receiver_interface

/* <add-type id="ieee_802_15_4_probe_snoop_t"></add-type> */
typedef void (*ieee_802_15_4_probe_snoop_t)(
                                lang_void *user_data,
                                conf_object_t *probe,
                                ieee_802_15_4_probe_side_t to_side,
                                const frags_t *frame,
                                uint32 rssi,
                                uint16 channel_page,
                                uint16 channel_number,
                                ieee_802_15_4_frame_crc_status_t crc_status);

/* <add id="ieee_802_15_4_probe_interface_t">
   <insert id="ieee_802_15_4_probe_snoop_t"/>
   <insert id="ieee_802_15_4_probe_side_t"/>
   <insert-until text="// ADD INTERFACE ieee_802_15_4_probe_interface"/>

   The <iface>ieee_802_15_4_probe</iface> interface is implemented by the
   IEEE 802.15.4 probe devices that provide an interface for Simics users to
   register their own callback to listen to the traffic going-on in the probe.
   The <fun>attach_snooper</fun> attaches a snooper function. The probe will
   pass each frame to the snooper function, then forward it unchanged where it
   should be going.
   The <fun>detach</fun> detaches the currently registered callback from
   the probe.

   This interface should only be used for inspection, and never as part of
   the actual simulation. The snoop functions must not affect the simulation
   in any way.
   The user_data parameter is passed to the snoop function every time
   it is called.

   </add>
   <add id="ieee_802_15_4_probe_interface_exec_context">
   Cell Context for all methods.
   </add>
*/
SIM_INTERFACE(ieee_802_15_4_probe) {
        void (*attach_snooper)(conf_object_t *NOTNULL probe,
                               ieee_802_15_4_probe_snoop_t snoop_fun,
                               lang_void *user_data);
        void (*detach)(conf_object_t *NOTNULL probe);
};
#define IEEE_802_15_4_PROBE_INTERFACE "ieee_802_15_4_probe"
// ADD INTERFACE ieee_802_15_4_probe_interface

#ifdef __cplusplus
}
#endif

#endif /* ! IEEE_802_15_4_INTERFACES_H */
