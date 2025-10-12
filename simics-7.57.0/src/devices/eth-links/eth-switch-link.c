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

#include <simics/device-api.h>
#include <simics/devs/ethernet.h>
#include <simics/util/hashtab.h>

#include "common.h"

static conf_class_t *ep_cls; /* the eth-switch link endpoint class */

static conf_class_t *snoop_ep_cls; /* the eth-switch snoop endpoint class */

typedef struct {
        common_link_t clink;
        ht_int_table_t snoops; /* IDs of all snoop endpoints */
} switch_link_t;

typedef struct {
        uint16 id;
        bool is_trunk;
} vlan_t;

typedef struct {
        common_link_endpoint_t cep;

        /* A table mapping destination (VLAN, MAC address) to endpoint. The
           values are endpoint IDs. */
        ht_int_table_t switch_table;

        vlan_t vlan;
} switch_ep_t;

typedef struct {
        common_link_endpoint_t cep;
        ethernet_link_snoop_t snoop_fun;
        lang_void *user_data;
        vlan_t vlan;
} snoop_ep_t;

typedef enum {
        Sw_Frame,                            /* Ethernet Frame */
        Sw_Unlearn_Ep_Id,                    /* Ep_Id disconnected */
} switch_message_type_t;

typedef struct {
        bool present;
        union {
                uint16 tci;
                struct  {
                        uint16 vid:12;
                        uint16 dei:1;
                        uint16 pcp:3;
                };
        };
} vlan_tag_t;

typedef struct {
        link_message_t common;
        switch_message_type_t msgtype;
        uint64 src_epid;                     /* Sender's endpoint ID */
        struct {                             /* Frame */
                vlan_tag_t vlan_tag;
                bytes_t bytes;
                bool crc_correct;
        } frame;
} switch_link_message_t;

/* Illegal VLAN ID. Used in Simics to mark a trunk that has no native VLAN ID.
   Result: All exiting packets will be VLAN tagged unless they arrived untagged
   on a trunk without a native VLAN ID */
#define NO_VLAN_ID 0xffff

static vlan_tag_t
absent_vlan_tag()
{
        return (vlan_tag_t){
                .present = false,
                .tci = 0};
}

static vlan_tag_t
present_vlan_tag(uint16 vid, uint16 dei, uint16 pcp)
{
        return (vlan_tag_t){
                .present = true,
                .vid = vid,
                .dei = dei,
                .pcp = pcp};
}

static vlan_tag_t
vlan_tag_from_vlan_id(uint16 vlan_id)
{
        if (vlan_id == NO_VLAN_ID)
                return absent_vlan_tag();
        else
                return present_vlan_tag(vlan_id, 0, 0);
}

static uint16
vlan_id_from_vlan_tag(vlan_tag_t vlan_tag)
{
        if (vlan_tag.present)
                return vlan_tag.vid;
        else
                return NO_VLAN_ID;
}

static attr_value_t
attr_encode_vlan_tag(vlan_tag_t vlan_tag)
{
        if (vlan_tag.present)
                return SIM_make_attr_uint64(
                        vlan_tag.vid
                        | ((uint64)vlan_tag.dei << 16)
                        | ((uint64)vlan_tag.pcp << 17));
        else
                return SIM_make_attr_uint64(NO_VLAN_ID);
}

static vlan_tag_t
attr_decode_vlan_tag(attr_value_t attr_value)
{
        uint64 value = SIM_attr_integer(attr_value);
        if (value == NO_VLAN_ID)
                return absent_vlan_tag();
        else
                return present_vlan_tag(
                        value & 0xfff,
                        (value >> 16) & 0x1,
                        (value >> 17) & 0x7);
}

static char *
eth_mac_str(const uint8 *mac, char *buffer, int len)
{
        snprintf(buffer, len, "%02x:%02x:%02x:%02x:%02x:%02x",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        return buffer;
}

static int
parse_eth_mac(const char *str, uint8 *mac)
{
        int m[6];
        int i;

        if (sscanf(str, "%x:%x:%x:%x:%x:%x",
                   &m[0], &m[1], &m[2], &m[3], &m[4], &m[5]) != 6)
                return 0;
        for (i = 0; i < 6; i++)
                mac[i] = m[i];
        return 1;
}

/* Create a new frame message, taking ownership of the given data. */
static link_message_t *
new_vlan_frame_message(uint64 src_epid, vlan_tag_t vlan_tag, size_t len,
                       const void *data)
{
        switch_link_message_t *msg = MM_MALLOC(1, switch_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = Sw_Frame;
        msg->src_epid = src_epid;
        msg->frame.vlan_tag = vlan_tag;
        msg->frame.bytes.len = len;
        msg->frame.bytes.data = data;
        msg->frame.crc_correct = true;  // invalid frames are dropped
        return &msg->common;
}

static link_message_t *
new_unlearn_message(uint64 src_epid)
{
        switch_link_message_t *msg = MM_MALLOC(1, switch_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = Sw_Unlearn_Ep_Id;
        msg->src_epid = src_epid;
        return &msg->common;
}

static void
free_message(conf_object_t *link, link_message_t *_msg)
{
        switch_link_message_t *msg = (switch_link_message_t *)_msg;
        if (msg->msgtype == Sw_Frame)
                MM_FREE((uint8 *)msg->frame.bytes.data);
        MM_FREE(msg);
}

static attr_value_t
switch_msg_to_attr(conf_object_t *link, const link_message_t *msgdata)
{
        switch_link_message_t *msg = (switch_link_message_t *)msgdata;
        switch (msg->msgtype) {
        case Sw_Frame:
                return SIM_make_attr_list(
                        5,
                        SIM_make_attr_string("frame"),
                        attr_encode_vlan_tag(msg->frame.vlan_tag),
                        SIM_make_attr_data(msg->frame.bytes.len,
                                           msg->frame.bytes.data),
                        SIM_make_attr_boolean(msg->frame.crc_correct),
                        SIM_make_attr_uint64(msg->src_epid));
        case Sw_Unlearn_Ep_Id:
                return SIM_make_attr_list(
                        2,
                        SIM_make_attr_string("unlearn_ep_id"),
                        SIM_make_attr_uint64(msg->src_epid));
        default:
                ASSERT(false);
        }
}

static link_message_t *
switch_msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        const char *typestr = SIM_attr_string(SIM_attr_list_item(attr, 0));
        if (strcmp(typestr, "frame") == 0) {
                vlan_tag_t vlan_tag=
                        attr_decode_vlan_tag(SIM_attr_list_item(attr, 1));
                attr_value_t frame_a = SIM_attr_list_item(attr, 2);
                // crc_correct no longer used, SIM_attr_list_item(attr, 3);
                uint8 *frame = MM_MALLOC(SIM_attr_data_size(frame_a), uint8);
                memcpy(frame, SIM_attr_data(frame_a),
                       SIM_attr_data_size(frame_a));
                uint64 src_epid;
                if (SIM_attr_list_size(attr) == 5)
                        src_epid = SIM_attr_integer(
                                SIM_attr_list_item(attr, 4));
                else
                        src_epid = LINK_NULL_ID;
                return new_vlan_frame_message(
                        src_epid, vlan_tag, SIM_attr_data_size(frame_a),
                        frame);
        } else if (strcmp(typestr, "unlearn_ep_id") == 0) {
                uint64 epid = SIM_attr_integer(SIM_attr_list_item(attr, 1));
                return new_unlearn_message(epid);
        } else {
                /* these are message from the previous eth-switch protocol that
                   can be ignored */
                ASSERT(strcmp(typestr, "unlearn") == 0
                       || strcmp(typestr, "learn") == 0);
                return NULL;
        }
}

static void
switch_marshal(conf_object_t *link, const link_message_t *_msg,
              void (*finish)(void *data, const frags_t *msg),
              void *finish_data)
{
        const switch_link_message_t *msg = (switch_link_message_t *)_msg;
        uint32 msgtype;
        uint8 data[8 + 1 + 2 + 1];

        STORE_BE32(&msgtype, msg->msgtype);
        frags_t buf;
        frags_init_add(&buf, &msgtype, 4);

        switch (msg->msgtype) {
        case Sw_Frame:
                UNALIGNED_STORE_BE64(data, msg->src_epid);
                UNALIGNED_STORE_BE8(data + 8, msg->frame.vlan_tag.present);
                UNALIGNED_STORE_BE16(data + 9, msg->frame.vlan_tag.tci);
                UNALIGNED_STORE_BE8(data + 11, msg->frame.crc_correct);
                frags_add(&buf, data, sizeof data);
                frags_add(&buf, msg->frame.bytes.data,
                          msg->frame.bytes.len);
                break;
        case Sw_Unlearn_Ep_Id:
                UNALIGNED_STORE_BE64(data, msg->src_epid);
                frags_add(&buf, data, 8);
                break;
        }

        finish(finish_data, &buf);
}

static link_message_t *
switch_unmarshal(conf_object_t *link, const frags_t *msg)
{
        size_t msg_len = frags_len(msg);

        ASSERT(msg_len >= 4);
        switch_message_type_t msgtype = frags_extract_be32(msg, 0);

        if (msgtype == Sw_Frame) {
                uint64 src_epid = frags_extract_be64(msg, 4);
                vlan_tag_t vlan_tag = {
                        .present = frags_extract_8(msg, 12),
                        .tci = frags_extract_be16(msg, 13)};
                // crc_correct no longer used, frags_extract_8(msg, 15);
                size_t frame_len = msg_len - 16;
                uint8 *frame_data =
                        frags_extract_slice_alloc(msg, 16, frame_len);
                return new_vlan_frame_message(src_epid, vlan_tag, frame_len,
                                              frame_data);
        } else {
                ASSERT(msgtype == Sw_Unlearn_Ep_Id);
                ASSERT(msg_len == 4 + 8);
                uint64 epid = frags_extract_be64(msg, 4);
                return new_unlearn_message(epid);
        }
}

/* Convert a (vlan-id, mac) pair to/from an uint64 */
static uint64
mac_to_int(uint16 vlan_id, const uint8 *mac)
{
        return (uint64)vlan_id << 48
                | (uint64)UNALIGNED_LOAD16(mac) << 32
                | UNALIGNED_LOAD32(mac + 2);
}

static void
int_to_mac(uint64 i, uint16 *vlan_id, uint8 *mac)
{
        *vlan_id = i >> 48;
        UNALIGNED_STORE16(mac, (i >> 32) & 0xffff);
        UNALIGNED_STORE32(mac + 2, i & 0xffffffff);
}

static void
learn(conf_object_t *link, switch_ep_t *ep, vlan_tag_t vlan_tag,
      const uint8 mac[6], uint64 src_epid)
{
        /* ignore cases where the message did not contain the source id
           (probably an old checkpointed frame) */
        if (src_epid == LINK_NULL_ID)
                return;

        switch_ep_t *swep = (switch_ep_t *)ep;
        uint64 key = mac_to_int(vlan_id_from_vlan_tag(vlan_tag), mac);
        uint64 *value = ht_lookup_int(&swep->switch_table, key);
        if (!value) {
                value = MM_ZALLOC(1, uint64);
                ht_insert_int(&swep->switch_table, key, value);
        }
        if (*value != src_epid) {
                char buf[20];
                SIM_LOG_INFO(2, &ep->cep.obj, 0,
                             "learning that %s belongs to %#llx",
                             eth_mac_str(mac, buf, sizeof buf),
                             src_epid);
        }
        *value = src_epid;
}

static void
unlearn(conf_object_t *link, conf_object_t *ep, uint64 epid)
{
        switch_ep_t *swep = (switch_ep_t *)ep;

        /* go through all known (vlan/MAC, endpoint id) pairs and remove all
           pairs matching epid */
        HT_FOREACH_INT(&swep->switch_table, it) {
                uint64 *value = ht_iter_int_value(it);
                if (*value == epid) {
                        uint64 key = ht_iter_int_key(it);
                        uint8 mac[6];
                        uint16 vlan_id;
                        int_to_mac(key, &vlan_id, mac);
                        char buf[20];
                        SIM_LOG_INFO(2, ep, 0,
                                     "unlearning that %s belonged to %#llx",
                                     eth_mac_str(mac, buf, sizeof buf),
                                     epid);
                        ht_remove_int(&swep->switch_table, key);
                        MM_FREE(value);
                }
        }
}

/* <add id="esw_deliver"><insert-until text="// esw_deliver_end"/></add> */
static void
switch_deliver_frame(conf_object_t *link, conf_object_t *ep,
                     vlan_tag_t vlan_tag, uint64 src_epid,
                     const frags_t *frame)
{
        eth_frame_crc_status_t crc_status = Eth_Frame_CRC_Match;

        if (SIMLINK_endpoint_is_device(ep)) {
                switch_ep_t *swep = (switch_ep_t *)ep;
                if (frags_len(frame) > 12) {
                        uint8 src_mac[6];
                        frags_extract_slice(frame, src_mac, 6, 6);
                        learn(link, swep, vlan_tag, src_mac, src_epid);
                }
                swep->cep.ifc->frame(SIMLINK_endpoint_device(ep), frame,
                                     crc_status);
        } else {
                snoop_ep_t *snoop = (snoop_ep_t *)ep;
                deliver_to_snoop(snoop->snoop_fun, snoop->user_data,
                                 SIMLINK_endpoint_clock(ep), frame,
                                 crc_status);
        }
}
// esw_deliver_end <- jdocu insert-until marker

#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

/*
 * Delivery between two endpoints  with no VLAN configured.
 * No VLAN tag was present and no VLAN ID is configured in the endpoint.
 */
static bool
is_standard_deliver(vlan_tag_t msg_vlan_tag, const vlan_t *ep_vlan)
{
        return (!msg_vlan_tag.present && (ep_vlan->id == NO_VLAN_ID));
}

/* Delivery from either an untagged port (non-trunk)
 * to an untagged port (non-trunk) with the same VLAN ID, or
 * from a tagged port (trunk) to a tagged port (trunk) with
 * the same native VID (native VLAN) (Note: the VLAN tag could have
 * been stripped away).
 */
static bool
is_matching_vlan(vlan_tag_t msg_vlan_tag, const vlan_t *ep_vlan)
{
        return ((msg_vlan_tag.present && (msg_vlan_tag.vid == ep_vlan->id)));
}

/* Delivery from an untagged port (non-trunk) to an untagged port (non-trunk)
 * with the message VLAN tag VID different from the endpoint native VID
 * (Non-native delivery).
 */
static bool
is_non_native(switch_link_message_t *msg, const vlan_t *ep_vlan)
{
        return  (ep_vlan->is_trunk
                && msg->frame.bytes.len >= 12
                && msg->frame.vlan_tag.present
                && (msg->frame.vlan_tag.vid != ep_vlan->id));
}

/* packet from switch to endpoint */
static void
deliver_switch(conf_object_t *ep, const link_message_t *msgdata)
{
        vlan_t *vlan;
        if (SIMLINK_endpoint_is_device(ep)) {
                switch_ep_t *swep = (switch_ep_t *)ep;
                vlan = &swep->vlan;
        } else {
                snoop_ep_t *snep = (snoop_ep_t *)ep;
                vlan = &snep->vlan;
        }
        conf_object_t *link = SIMLINK_endpoint_link(ep);
        uint8 buf[1000];
        SIM_LOG_INFO(3, ep, 0, "delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        switch_link_message_t *msg = (switch_link_message_t *)msgdata;
        switch (msg->msgtype) {
        case Sw_Frame:
                if (is_standard_deliver(msg->frame.vlan_tag, vlan)) {
                        frags_t frame;
                        frags_init_add(&frame, msg->frame.bytes.data,
                                       msg->frame.bytes.len);
                        switch_deliver_frame(link, ep, msg->frame.vlan_tag,
                                             msg->src_epid, &frame);
                }
                else if (is_matching_vlan(msg->frame.vlan_tag, vlan)) {
                        /* Delivery to same VLAN, so we don't 802.1Q tag it. */
                        frags_t frame;

                        /* Tag could have been stripped on ingress, so pad
                           frame with zeroes _before_ the CRC/FCS field */
                        frags_init_add(&frame, msg->frame.bytes.data,
                                       msg->frame.bytes.len - 4); // except CRC

                        const uint8 pad[4] = { 0, 0, 0, 0 };
                        if (msg->frame.bytes.len < 64)
                                frags_add(&frame, pad, 4);

                        frags_add(&frame, msg->frame.bytes.data
                                  + msg->frame.bytes.len - 4, 4); // CRC

                        switch_deliver_frame(link, ep, msg->frame.vlan_tag,
                                             msg->src_epid, &frame);
                } else if (is_non_native(msg, vlan)) {
                        /* Non-native delivery to a trunk port, so we have to
                           insert an 802.1Q tag. (If the packet is associated
                           with a VLAN) */
                        frags_t frame;
                        uint16 vlan_tag[2];
                        STORE_BE16(&vlan_tag[0], 0x8100); /* TPID */
                        STORE_BE16(&vlan_tag[1], msg->frame.vlan_tag.tci);
                        frags_init_add(&frame, msg->frame.bytes.data, 12);
                        frags_add(&frame, vlan_tag, sizeof(vlan_tag));
                        int hdr = UNALIGNED_LOAD_BE16(msg->frame.bytes.data
                                                      + 12) == 0x8100
                                ? 16  /* there was an existing tag; drop it */
                                : 12; /* no existing tag */
                        frags_add(&frame, msg->frame.bytes.data + hdr,
                                  msg->frame.bytes.len - hdr);
                        switch_deliver_frame(link, ep, msg->frame.vlan_tag,
                                             msg->src_epid, &frame);
                } else {
                        /* Ignore the frame since it's not on our VLAN. */
                }
                break;
        case Sw_Unlearn_Ep_Id:
                if (SIMLINK_endpoint_is_device(ep))
                        unlearn(link, ep, msg->src_epid);
                break;
        }
}

static void
link_config_value_updated(conf_object_t *link, const char *key, const frags_t *msg)
{
        switch_link_t *swlink = (switch_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);
        ht_update_int(&swlink->snoops, ep_id, NULL);
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        switch_link_t *swlink = (switch_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);
        ht_remove_int(&swlink->snoops, ep_id);
}

static attr_value_t
vlan_ep_attrs(uint16 vlan_id, bool is_vlan_trunk)
{
        return SIM_make_attr_list(
                2,
                SIM_make_attr_list(2,
                                   SIM_make_attr_string("vlan_id"),
                                   vlan_id == NO_VLAN_ID
                                   ? SIM_make_attr_nil()
                                   : SIM_make_attr_uint64(vlan_id)),
                SIM_make_attr_list(2,
                                   SIM_make_attr_string("vlan_trunk"),
                                   SIM_make_attr_boolean(is_vlan_trunk)));
}

static conf_object_t *
vlan_attach_snoop(conf_object_t *link_obj, conf_object_t *clock,
                  ethernet_link_snoop_t snoop_fun, lang_void *user_data,
                  uint16 vlan_id, bool is_vlan_trunk)
{
        switch_link_t *swlink = (switch_link_t *)link_obj;
        attach_snoop_helper(&swlink->clink, clock);
        attr_value_t attrs = vlan_ep_attrs(vlan_id, is_vlan_trunk);
        snoop_ep_t *snoop = (snoop_ep_t *)SIMLINK_snoop_endpoint_create(
                snoop_ep_cls, link_obj, clock, attrs);
        SIM_attr_free(&attrs);
        snoop->snoop_fun = snoop_fun;
        snoop->user_data = user_data;
        return &snoop->cep.obj;
}

static conf_object_t *
attach_snoop(conf_object_t *obj, conf_object_t *clock,
             ethernet_link_snoop_t snoop_fun, lang_void *user_data)
{
        return vlan_attach_snoop(obj, clock, snoop_fun, user_data,
                                 NO_VLAN_ID, true);
}

static conf_object_t *
switch_link_alloc_object(void *data)
{
        switch_link_t *swlink = MM_ZALLOC(1, switch_link_t);
        return &swlink->clink.obj;
}

static void
switch_pre_delete_instance(conf_object_t *obj)
{
        switch_link_t *swlink = (switch_link_t *)obj;
        tear_down_network_breakpoints(&swlink->clink);
        common_pre_delete_instance(obj);
}

static void *
switch_link_init_object(conf_object_t *obj, void *data)
{
        static const link_type_t switch_link_type = {
                .free_msg = free_message,
                .msg_to_attr = switch_msg_to_attr,
                .msg_from_attr = switch_msg_from_attr,
                .marshal = switch_marshal,
                .unmarshal = switch_unmarshal,
                .deliver = deliver_switch,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
                .device_changed = ep_device_changed
        };
        static const eth_funcs_t switch_eth_funcs = {
                .new_frame_message = 0
        };

        switch_link_t *swlink = (switch_link_t *)obj;
        common_eth_link_init(&swlink->clink,
                             &switch_link_type, &switch_eth_funcs);
        ht_init_int_table(&swlink->snoops);
        swlink->clink.bpds = NULL;
        return swlink;
}

static conf_object_t *
switch_ep_alloc_object(void *data)
{
        switch_ep_t *swep = MM_ZALLOC(1, switch_ep_t);
        return &swep->cep.obj;
}

static void *
switch_ep_init_object(conf_object_t *obj, void *data)
{
        switch_ep_t *swep = (switch_ep_t *)obj;
        common_eth_ep_constructor(&swep->cep, false);
        ht_init_int_table(&swep->switch_table);
        return swep;
}

static void
switch_ep_pre_delete_instance(conf_object_t *obj)
{
        switch_ep_t *swep = (switch_ep_t *)obj;
        /* broadcast a message to indicate that the endpoint is being
           disconnected, but only if this endpoint was ever connected to a
           device */
        if (SIMLINK_endpoint_device(obj)) {
                link_message_t *msg =
                        new_unlearn_message(SIMLINK_endpoint_id(obj));
                SIMLINK_send_message(obj, LINK_BROADCAST_ID, msg);
        }
        common_eth_ep_destructor(&swep->cep);
}

static int
switch_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

static conf_object_t *
snoop_ep_alloc_object(void *data)
{
        snoop_ep_t *snep = MM_ZALLOC(1, snoop_ep_t);
        return &snep->cep.obj;
}

static void *
snoop_ep_init_object(conf_object_t *obj, void *data)
{
        snoop_ep_t *snep = (snoop_ep_t *)obj;
        common_eth_ep_constructor(&snep->cep, true);
        return snep;
}

/* <add id="esw_ep_finalize"><insert-upto text="}"/></add> */
static void
snoop_ep_finalize_instance(conf_object_t *ep)
{
        ep_finalize_instance(ep);

        /* Tell all endpoints that there's a new snoop in town. */
        char ep_id[17];
        snprintf(ep_id, sizeof(ep_id), "%llx", SIMLINK_endpoint_id(ep));
        frags_t value;
        frags_init(&value); /* empty value, just to put the
                               key in the database */
        SIMLINK_config_update_value(
                SIMLINK_endpoint_link(ep), ep_id, &value);
}

static void
snoop_ep_pre_delete_instance(conf_object_t *ep)
{
        snoop_ep_t *snep = (snoop_ep_t *)ep;

        /* Tell all endpoints that this snoop is gone now. */
        char ep_id[17];
        snprintf(ep_id, sizeof(ep_id), "%llx", SIMLINK_endpoint_id(ep));
        SIMLINK_config_remove_value(SIMLINK_endpoint_link(ep), ep_id);

        common_eth_ep_destructor(&snep->cep);
}

static int
snoop_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

/* Return the target endpoint id or LINK_BROADCAST_ID */
static uint64
get_destination_ep(switch_ep_t *swep, vlan_tag_t vlan_tag,
                   const frags_t *frame)
{
        if (frags_len(frame) < 6)
                return LINK_BROADCAST_ID;

        uint8 dst_mac[6];
        frags_extract_slice(frame, dst_mac, 0, 6);

        uint16 vlan_id = vlan_tag.present ? vlan_tag.vid : NO_VLAN_ID;
        uint64 key = mac_to_int(vlan_id, dst_mac);
        uint64 *value = ht_lookup_int(&swep->switch_table, key);
        return value ? *value : LINK_BROADCAST_ID;
}

/* packet from endpoint to switch */
static void
switch_send_frame(conf_object_t *ep, const frags_t *frame,
                  eth_frame_crc_status_t crc_status)
{
        switch_ep_t *swep = (switch_ep_t *)ep;
        switch_link_t *swlink = (switch_link_t *)SIMLINK_endpoint_link(ep);
        vlan_tag_t vlan_tag = vlan_tag_from_vlan_id(swep->vlan.id);

        /* Transform CRC_Unknown into either Match or Mismatch */
        bool crc_correct = crc_status == Eth_Frame_CRC_Unknown
                ? check_crc(frame)
                : (crc_status == Eth_Frame_CRC_Match);

        if (!crc_correct) {
                SIM_LOG_INFO(
                        2, ep, 0,
                        "Dropping frame with incorrect FCS");
                return;
        }

        /* If the packet contains an 802.1Q VLAN ID tag, we need to extract the
           tag and edit it out of the packet. */
        frags_t modified_frame;
        if (frags_len(frame) >= 16
            && frags_extract_be16(frame, 12) == 0x8100) {
                /* VLAN ID 0 is actually a priority tag and not a VLAN tag.
                   There was previously some handling of it here (not stripped
                   as VLAN tags are) but support for it was missing in other
                   places. Better not handle it until properly tested. */
                if (!swep->vlan.is_trunk) {
                        SIM_LOG_INFO(
                                1, ep, 0,
                                "Frame with 802.1Q tag sent from"
                                " non-trunk endpoint; dropping it");
                        return;
                }

                /* Use the VLAN ID, DEI and PCP from the packet
                   instead of the endpoint's native VLAN ID. */
                vlan_tag.present = true;
                vlan_tag.tci = frags_extract_be16(frame, 14);

                if (vlan_tag.vid == swep->vlan.id) {
                     uint8 buf[1000];
                     SIM_LOG_INFO(1, ep, 0, "Warning: link %s received a packet"
                                            " tagged with the same VID as the"
                                            " trunk port native VID: %d."
                                            " The 802.1Q VLAN tag will"
                                            " be stripped at egress.",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), swep->vlan.id);
                }

                /* Make a new packet without the 802.1Q VLAN ID tag. */
                frags_init_add_from_frags(&modified_frame, frame, 0, 12);
                frags_add_from_frags(&modified_frame, frame, 16,
                                     frags_len(frame) - 16);
                frame = &modified_frame;
        }

        uint64 dst_ep = get_destination_ep(swep, vlan_tag, frame);
        link_message_t *msg = new_vlan_frame_message(
                SIMLINK_endpoint_id(ep), vlan_tag, frags_len(frame),
                frags_extract_alloc(frame));

        if (dst_ep == LINK_BROADCAST_ID) {
                SIM_LOG_INFO(3, ep, 0,
                             "(ep %#llx) broadcasting frame (%zu bytes)",
                             SIMLINK_endpoint_id(ep), frags_len(frame));
                SIMLINK_send_message(ep, dst_ep, msg);
        } else {
                SIM_LOG_INFO(3, ep, 0,
                             "(ep %#llx) sending frame to %#llx"
                             " (%zu bytes)",
                             SIMLINK_endpoint_id(ep), dst_ep, frags_len(frame));
                int num_dsts = 1 + ht_num_entries_int(&swlink->snoops);
                uint64 dst_ids[num_dsts];
                dst_ids[0] = dst_ep;
                int i = 1;
                HT_FOREACH_INT(&swlink->snoops, it)
                        dst_ids[i++] = ht_iter_int_key(it);
                SIMLINK_send_message_multi(ep, num_dsts, dst_ids, msg);
        }
}

static attr_value_t
get_ep_switch_table(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        switch_ep_t *swep = (switch_ep_t *)obj;
        char buf[20];
        attr_value_t lst = SIM_alloc_attr_list(
                ht_num_entries_int(&swep->switch_table));
        int i = 0;
        HT_FOREACH_INT(&swep->switch_table, it) {
                uint16 vlan_id;
                uint8 mac[6];
                int_to_mac(ht_iter_int_key(it), &vlan_id, mac);
                uint64 *valuep = ht_iter_int_value(it);
                SIM_attr_list_set_item(
                        &lst, i,
                        SIM_make_attr_list(
                                3,
                                SIM_make_attr_uint64(vlan_id),
                                SIM_make_attr_string(
                                        eth_mac_str(mac, buf, sizeof buf)),
                                SIM_make_attr_uint64(*valuep)));
                i++;
        }
        return lst;
}

static set_error_t
set_ep_switch_table(void *user_data, conf_object_t *obj,
                    attr_value_t *val, attr_value_t *idx)
{
        switch_ep_t *swep = (switch_ep_t *)obj;
        ht_int_table_t new_table;
        ht_init_int_table(&new_table);
        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                attr_value_t v = SIM_attr_list_item(*val, i);
                uint16 vlan_id;
                if (SIM_attr_is_nil(SIM_attr_list_item(v, 0))) {
                        /* This is an old entry for a trunk endpoint, ignore
                           it */
                        continue;
                } else {
                        vlan_id = SIM_attr_integer(SIM_attr_list_item(v, 0));
                }
                uint8 mac[6];
                if (!parse_eth_mac(SIM_attr_string(SIM_attr_list_item(v, 1)),
                                   mac)) {
                        SIM_attribute_error("malformed MAC address");
                        ht_delete_int_table(&new_table, true);
                        return Sim_Set_Illegal_Value;
                }
                uint64 epid = SIM_attr_integer(SIM_attr_list_item(v, 2));
                uint64 key = mac_to_int(vlan_id, mac);
                uint64 *value = MM_MALLOC(1, uint64);
                *value = epid;
                ht_insert_int(&new_table, key, value);
        }
        ht_delete_int_table(&swep->switch_table, true);
        swep->switch_table = new_table;
        return Sim_Set_Ok;
}

typedef struct {
        vlan_t *(*obj_to_vlan)(conf_object_t *obj);
} obj_to_vlan_t;

static vlan_t *
get_vlan(obj_to_vlan_t *otv, conf_object_t *obj)
{
        return otv->obj_to_vlan(obj);
}

static vlan_t *
get_ep_vlan(conf_object_t *obj)
{
        switch_ep_t *swep = (switch_ep_t *)obj;
        return &swep->vlan;
}

static vlan_t *
get_snoop_vlan(conf_object_t *obj)
{
        snoop_ep_t *snep = (snoop_ep_t *)obj;
        return &snep->vlan;
}

static attr_value_t
get_ep_vlan_id(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        vlan_t *vlan = get_vlan(user_data, obj);
        if (vlan->id == NO_VLAN_ID)
                return SIM_make_attr_nil();
        else
                return SIM_make_attr_uint64(vlan->id);
}

static set_error_t
set_ep_vlan_id(void *user_data, conf_object_t *obj,
               attr_value_t *val, attr_value_t *idx)
{
        if (SIM_object_is_configured(obj))
                return Sim_Set_Not_Writable;

        vlan_t *vlan = get_vlan(user_data, obj);
        uint16 vlan_id = NO_VLAN_ID;

        if (SIM_attr_is_nil(*val)) {
                if (!vlan->is_trunk)
                        return Sim_Set_Illegal_Value;
        } else {
                vlan_id = SIM_attr_integer(*val);
                if (vlan_id == 0 || vlan_id > 4095)
                        return Sim_Set_Illegal_Value;
        }

        vlan->id = vlan_id;
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_vlan_trunk(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        vlan_t *vlan = get_vlan(user_data, obj);
        return SIM_make_attr_boolean(vlan->is_trunk);
}

static set_error_t
set_ep_vlan_trunk(void *user_data, conf_object_t *obj,
                  attr_value_t *val, attr_value_t *idx)
{
        if (SIM_object_is_configured(obj))
                return Sim_Set_Not_Writable;
        vlan_t *vlan = get_vlan(user_data, obj);
        vlan->is_trunk = SIM_attr_boolean(*val);
        return Sim_Set_Ok;
}

static void
register_vlan_attrs(conf_class_t *cls, obj_to_vlan_t *otv)
{
        SIM_register_typed_attribute(
                cls, "vlan_trunk",
                get_ep_vlan_trunk, otv, set_ep_vlan_trunk, otv,
                Sim_Attr_Required, "b", NULL,
                "Set to true if the endpoint is a trunk.");
        SIM_register_typed_attribute(
                cls, "vlan_id", get_ep_vlan_id, otv, set_ep_vlan_id, otv,
                Sim_Attr_Required, "i|n", NULL,
                "The VLAN ID of the endpoint. If the endpoint is a trunk, the"
                " value is the native VLAN ID (1 - 4095) or None if the"
                " trunk should not have any native ID. Note: this is not the"
                " allowed VIDs that the port can handle. By default, trunk"
                " ports can handle all VIDs.");
        SIM_ensure_partial_attr_order(cls, "vlan_trunk", "vlan_id");
}

static int64
switch_bp_add(conf_object_t *obj, bytes_t src_mac, bytes_t dst_mac,
              int eth_type, break_net_cb_t cb, bool once, int64 bp_id)
{
        switch_link_t *sl = SIM_object_data(obj);
        return bp_add(obj, src_mac, dst_mac, eth_type, cb, &(sl->clink),
                      bp_id, once);
}

static void
switch_bp_remove(conf_object_t *obj, int64 bp_id)
{
        switch_link_t *sl = SIM_object_data(obj);
        bp_remove(obj, &(sl->clink), bp_id);
}

void
init_eth_switch_link()
{
        const class_data_t link_cls_funcs = {
                .alloc_object = switch_link_alloc_object,
                .init_object = switch_link_init_object,
                .finalize_instance = link_finalize_instance,
                .pre_delete_instance = switch_pre_delete_instance,
                .delete_instance = common_delete_instance,
                .class_desc = "model of switched Ethernet link",
                .description = "Switched Ethernet link"
        };

        conf_class_t *link_cls = SIM_register_class("eth-switch-link",
                                                    &link_cls_funcs);
        SIMLINK_register_class(link_cls);
        register_ethernet_common_link_interfaces(link_cls, attach_snoop);
        static const ethernet_vlan_snoop_interface_t vlan_snoop_iface = {
                .attach = vlan_attach_snoop,
        };
        SIM_register_interface(link_cls, ETHERNET_VLAN_SNOOP_INTERFACE,
                               &vlan_snoop_iface);

        const class_data_t ep_cls_funcs = {
                .alloc_object = switch_ep_alloc_object,
                .init_object = switch_ep_init_object,
                .finalize_instance = ep_finalize_instance,
                .pre_delete_instance = switch_ep_pre_delete_instance,
                .delete_instance = switch_ep_delete_instance,
                .class_desc = "an Ethernet switch link endpoint",
                .description = "Ethernet switch link endpoint"
        };
        ep_cls = SIM_register_class("eth-switch-link-endpoint", &ep_cls_funcs);
        /* The message type is impossible to type. */
        SIMLINK_register_endpoint_class(ep_cls, "a");
        register_ethernet_common_ep_interfaces(ep_cls, switch_send_frame);
        SIM_register_typed_attribute(
                ep_cls, "switch_table",
                get_ep_switch_table, NULL, set_ep_switch_table, NULL,
                Sim_Attr_Optional, "[[i|n,s,i]*]", NULL,
                "Map from destination VLAN and MAC address to endpoint ID");
        static obj_to_vlan_t otv = { .obj_to_vlan = get_ep_vlan };
        register_vlan_attrs(ep_cls, &otv);

        const class_data_t snoop_ep_cls_funcs = {
                .alloc_object = snoop_ep_alloc_object,
                .init_object = snoop_ep_init_object,
                .finalize_instance = snoop_ep_finalize_instance,
                .pre_delete_instance = snoop_ep_pre_delete_instance,
                .delete_instance = snoop_ep_delete_instance,
                .description = "Ethernet switch snoop endpoint",
                .class_desc = "an Ethernet switch snoop endpoint",
                .kind = Sim_Class_Kind_Pseudo,
        };
        snoop_ep_cls = SIM_register_class("eth-switch-link-snoop-endpoint",
                                          &snoop_ep_cls_funcs);
        SIMLINK_register_snoop_endpoint_class(snoop_ep_cls);
        static obj_to_vlan_t snoop_otv = { .obj_to_vlan = get_snoop_vlan };
        register_vlan_attrs(snoop_ep_cls, &snoop_otv);

        static const network_breakpoint_interface_t break_net = {
                .add    = switch_bp_add,
                .remove = switch_bp_remove,
        };
        SIM_REGISTER_INTERFACE(link_cls, network_breakpoint, &break_net);
}
