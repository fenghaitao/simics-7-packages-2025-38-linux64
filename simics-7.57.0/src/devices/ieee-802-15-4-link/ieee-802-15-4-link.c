/*
 * ieee-802-15-4-link.c

  © 2014 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/utils.h>
#include <simics/devs/liblink.h>
#include <simics/util/genrand.h>
#include "ieee-802-15-4-interfaces.h"
#include "crc.h"

/* the main link object type */
typedef struct {
        conf_object_t obj;  /* must start with a conf_object_t */

        ht_str_table_t node_table;  /* key: node name, value: endpoint id */
} ieee_802_15_4_link_t;

/* the endpoint object type */
typedef struct {
        conf_object_t obj;  /* must start with a conf_object_t */

        ht_int_table_t rssi_table;  /* key: endpoint id, value: RSSI */

        /* packet loss settings */
        uint8 rssi_always_drop;
        uint8 rssi_random_drop;
        uint8 rssi_random_drop_ratio;

        uint8 contention_ratio;  /* contention ratio */

        rand_state_t *random_state;  /* random number generator state */
} ieee_802_15_4_link_endpoint_t;

/* the message type */
typedef struct {
        link_message_t common;  /* must start with a link_message_t */

        bytes_t frame;  /* payload */
        uint32 rssi;  /* RSSI value */

        /* frequency channel */
        uint16 channel_page;
        uint16 channel_number;

        ieee_802_15_4_frame_crc_status_t crc_status;  /* CRC status */
} ieee_802_15_4_link_message_t;

static link_message_t *
new_ieee_802_15_4_message(const uint8 *data,
                          size_t len,
                          uint32 rssi,
                          uint16 channel_page,
                          uint16 channel_number,
                          ieee_802_15_4_frame_crc_status_t crc_status)
{
        uint8 *d;
        ieee_802_15_4_link_message_t *m;

        d = MM_MALLOC(len, uint8);
        m = MM_MALLOC(1, ieee_802_15_4_link_message_t);

        SIMLINK_init_message(&m->common);

        memcpy(d, data, len);
        m->frame = (bytes_t ){ .data = d, .len = len };
        m->rssi = rssi;
        m->channel_page = channel_page;
        m->channel_number = channel_number;
        m->crc_status = crc_status;

        return &m->common;
}

static void
free_msg(conf_object_t *link, link_message_t *lm)
{
        ieee_802_15_4_link_message_t *m;

        m = (ieee_802_15_4_link_message_t *)lm;
        MM_FREE((uint8 *)m->frame.data);
        m->frame.data = NULL;
        MM_FREE(m);
}

/* Convert a message to an attribute value. */
static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *lm)
{
        const ieee_802_15_4_link_message_t *m;

        m = (const ieee_802_15_4_link_message_t *)lm;
        return SIM_make_attr_list(5,
                                  SIM_make_attr_data(m->frame.len,
                                                     m->frame.data),
                                  SIM_make_attr_uint64(m->rssi),
                                  SIM_make_attr_uint64(m->channel_number),
                                  SIM_make_attr_uint64(m->channel_page),
                                  SIM_make_attr_uint64(m->crc_status));
}

/* Convert an attribute value to a message. */
static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        uint32 rssi;
        attr_value_t frame_attr;
        uint16 channel_page, channel_number;
        ieee_802_15_4_frame_crc_status_t crc_status;

        frame_attr = SIM_attr_list_item(attr, 0);
        rssi = SIM_attr_integer(SIM_attr_list_item(attr, 1));
        channel_page = SIM_attr_integer(SIM_attr_list_item(attr, 2));
        channel_number = SIM_attr_integer(SIM_attr_list_item(attr, 3));
        crc_status = SIM_attr_integer(SIM_attr_list_item(attr, 4));

        return new_ieee_802_15_4_message(SIM_attr_data(frame_attr),
                                         SIM_attr_data_size(frame_attr),
                                         rssi,
                                         channel_page,
                                         channel_number,
                                         crc_status);
}

/* Convert a message to a byte string, which is then passed to finish(). */
static void
marshal(conf_object_t *link,
        const link_message_t *lm,
        void (*finish)(void *data, const frags_t *msg),
        void *finish_data)
{
        const ieee_802_15_4_link_message_t *m;
        frags_t buf;
        uint8 bytes[12];

        m = (const ieee_802_15_4_link_message_t *)lm;
        frags_init_add(&buf, m->frame.data, m->frame.len);
        UNALIGNED_STORE_LE32(&bytes[0], m->rssi);
        UNALIGNED_STORE_LE16(&bytes[4], m->channel_page);
        UNALIGNED_STORE_LE16(&bytes[6], m->channel_number);
        UNALIGNED_STORE_LE32(&bytes[8], m->crc_status);
        frags_add(&buf, &bytes[0], 12);
        finish(finish_data, &buf);
}

/* Create a message from marshalled data. */
static link_message_t *
unmarshal(conf_object_t *link, const frags_t *data)
{
        size_t offset;
        uint32 rssi;
        uint16 channel_page;
        uint16 channel_number;
        ieee_802_15_4_frame_crc_status_t crc_status;
        /* 12 = rssi(4) + channel_page(2) + channel_number(2) + crc_status(4) */
        size_t frame_len = frags_len(data) - 12;
        uint8 frame_buf[frame_len];

        frags_extract_slice(data, frame_buf, 0, frame_len);
        offset = frame_len;
        rssi = frags_extract_le32(data, offset);
        offset += 4;
        channel_page = frags_extract_le16(data, offset);
        offset += 2;
        channel_number = frags_extract_le16(data, offset);
        offset += 2;
        crc_status = frags_extract_le32(data, offset);

        return new_ieee_802_15_4_message(frame_buf,
                                         frame_len,
                                         rssi,
                                         channel_page,
                                         channel_number,
                                         crc_status);
}

/* Deliver a message to the indicated endpoint. */
static void
deliver(conf_object_t *obj, const link_message_t *lm)
{
        const char *port;
        conf_object_t *dev;
        const ieee_802_15_4_link_message_t *m;
        const ieee_802_15_4_receiver_interface_t *dev_iface;
        bool to_deliver;
        ieee_802_15_4_link_endpoint_t *ep;

        m = (const ieee_802_15_4_link_message_t *)lm;
        if (m->rssi == 0) {
                SIM_LOG_ERROR(obj, 0, "invalid message");
                return;
        }
        SIM_LOG_INFO(3, obj, 0, "a message received (rssi = %u)", m->rssi);

        dev = SIMLINK_endpoint_device(obj);
        port = SIMLINK_endpoint_port(obj);
        dev_iface = SIM_C_GET_PORT_INTERFACE(dev, ieee_802_15_4_receiver, port);
        ep = (ieee_802_15_4_link_endpoint_t *)obj;

        if (m->rssi <= ep->rssi_always_drop) {
                SIM_LOG_INFO(4, obj, 0,
                             "rssi lower than rssi_always_drop = %d",
                             ep->rssi_always_drop);
                to_deliver = false;
        } else if (ep->rssi_random_drop < m->rssi) {
                to_deliver = true;
                SIM_LOG_INFO(4, obj, 0,
                             "rssi higher than rssi_random_drop = %d",
                             ep->rssi_random_drop);
        } else {
                /* boundary conditions special handling for intuition */
                if (ep->rssi_random_drop_ratio == 0)
                        to_deliver = true;
                else if (ep->rssi_random_drop_ratio == 100)
                        to_deliver = false;
                else {
                        uint64 p;

                        p = genrand_range(ep->random_state, 100);
                        to_deliver = (p > ep->rssi_random_drop_ratio);

                        SIM_LOG_INFO(4, obj, 0,
                                     "rand = %lld,"
                                     " rssi_random_drop_ratio = %d",
                                     p, ep->rssi_random_drop_ratio);
                }
        }

        if (to_deliver) {
                frags_t buf;

                SIM_LOG_INFO(3, obj, 0, "deliver the message to device");
                frags_init_add(&buf, m->frame.data, m->frame.len);
                dev_iface->receive(dev, &buf, m->rssi,
                                   m->channel_page,
                                   m->channel_number,
                                   m->crc_status);
        } else {
                SIM_LOG_INFO(3, obj, 0, "drop the message");
                dev_iface->frame_lost(dev, m->rssi,
                                      m->channel_page,
                                      m->channel_number);
        }
}

static void
link_config_value_updated(conf_object_t *link,
                          const char *key,
                          const frags_t *value)
{
        uint64 ep_id;
        uint64 *ep_id_p;
        ieee_802_15_4_link_t *ieee_802_15_4_link = (ieee_802_15_4_link_t *)link;

        frags_extract(value, &ep_id);
        ep_id_p = MM_ZALLOC(1, uint64);
        *ep_id_p = ep_id;
        if (ht_lookup_str(&ieee_802_15_4_link->node_table, key) == NULL) {
                SIM_LOG_INFO(3, link, 0,
                             "add node to node table:"
                             "node_name = %s, ep_id = %#llx",
                             key, ep_id);
                ht_insert_str(&ieee_802_15_4_link->node_table, key, ep_id_p);
        } else {
                SIM_LOG_INFO(3, link, 0,
                             "update node in node table:"""
                             " node_name = %s, ep_id = %#llx",
                             key, ep_id);
                ht_update_str(&ieee_802_15_4_link->node_table, key, ep_id_p);
        }
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        uint64 *ep_id_p;
        ieee_802_15_4_link_t *ieee_802_15_4_link;

        ieee_802_15_4_link = (ieee_802_15_4_link_t *)link;
        ep_id_p = (uint64 *)ht_lookup_str(&ieee_802_15_4_link->node_table, key);
        if (ep_id_p == NULL) {
                SIM_LOG_INFO(2, link, 0,
                             "node (node_name = %s) is not found", key);
                return;
        }

        SIM_LOG_INFO(3, link, 0,
                "remove node (node_name = %s, ep_id = %#llx)",
                key, *ep_id_p);
        ht_remove_str(&ieee_802_15_4_link->node_table, key);
        MM_FREE(ep_id_p);
}

/* The device attached to an endpoint has changed. */
static void
device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        const char *port;
        conf_object_t *dev;
        const char *node_name;
        const ieee_802_15_4_receiver_interface_t *dev_iface;

        SIM_LOG_INFO(3, ep, 0, "device changed");

        dev = SIMLINK_endpoint_device(ep);
        port = SIMLINK_endpoint_port(ep);
        node_name = SIM_object_name(dev);
        dev_iface = SIM_C_GET_PORT_INTERFACE(dev, ieee_802_15_4_receiver, port);

        if (dev_iface != NULL) {
                uint64 ep_id;
                frags_t value;
                conf_object_t *link;

                ep_id = SIMLINK_endpoint_id(ep);
                link = SIMLINK_endpoint_link(ep);
                SIM_LOG_INFO(3, ep, 0,
                             "send out configuration"
                             "(node_name = %s, ep_id = %#llx)",
                             node_name, ep_id);
                frags_init_add(&value, &ep_id, sizeof(ep_id));
                SIMLINK_config_update_value(link, node_name, &value);
        } else {
                SIM_LOG_ERROR(ep, 0,
                              "ieee_802_15_4_receiver unimplemented in %s",
                              node_name);
        }
}

static conf_object_t *
ieee_802_15_4_link_alloc_object(void *data)
{
        ieee_802_15_4_link_t *link = MM_ZALLOC(1, ieee_802_15_4_link_t);
        return &link->obj;
}

static void *
ieee_802_15_4_link_init_object(conf_object_t *obj, void *data)
{
        ieee_802_15_4_link_t *link = (ieee_802_15_4_link_t *)obj;

        static const link_type_t link_methods = {
                             .msg_to_attr = msg_to_attr,
                             .msg_from_attr = msg_from_attr,
                             .free_msg = free_msg,
                             .marshal = marshal,
                             .unmarshal = unmarshal,
                             .deliver = deliver,
                             .update_config_value = link_config_value_updated,
                             .remove_config_value = link_config_value_removed,
                             .device_changed = device_changed };

        SIMLINK_init(&link->obj, &link_methods);
        ht_init_str_table(&link->node_table, true);
        return &link->obj;
}

/* Called when the link object has been set up (all attributes set). */
static void
ieee_802_15_4_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
ieee_802_15_4_link_pre_delete_instance(conf_object_t *obj)
{
        ieee_802_15_4_link_t *link = (ieee_802_15_4_link_t *)obj;
        ht_delete_str_table(&link->node_table, true);
        SIMLINK_pre_delete(obj);
}

static int
ieee_802_15_4_link_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0;
}

/* 16-bit FCS based on ITU CRC: x ^ 16 + x ^ 12 + x ^ 5 + 1 */
static uint16
calc_crc16(const frags_t *frame)
{
        uint32 t = 0;
        uint8 input[frags_len(frame)];

        /* Convert the frame into an array. */
        frags_extract(frame, input);

        /* Check CRC. Skip PHY header. */
        for (int i = 1; i < sizeof(input); i++) {
                for (uint8 mask = 0x80; mask > 0; mask >>= 1) {
                        t <<= 1;

                        if ((t & 0x10000) != 0)
                                t ^= 0x11021;

                        if ((input[i] & mask) != 0)
                                t ^= 0x1021;
                }
        }

        return (t & 0xffff);
}

static ieee_802_15_4_transmit_status_t
transmit(conf_object_t *NOTNULL obj,
         const frags_t *frame,
         uint16 channel_page,
         uint16 channel_number,
         ieee_802_15_4_frame_crc_status_t crc_status)
{
        ieee_802_15_4_link_endpoint_t *ep;
        bool crc_correct;
        bool to_transmit;

        SIM_LOG_INFO(3, obj, 0, "transmit request received");

        if (crc_status == IEEE_802_15_4_Frame_CRC16_Unknown) {
                uint16 crc;

                crc = calc_crc16(frame);
                SIM_LOG_INFO(4, obj, 0, "compute crc16: crc = %#x", crc);
                crc_correct = (crc == 0);
        } else if (crc_status == IEEE_802_15_4_Frame_CRC32_Unknown) {
                if (frags_len(frame) > 4) {
                        uint32 crc;

                        crc = get_ethernet_crc_frags(frame);
                        SIM_LOG_INFO(4, obj, 0, "check crc: crc32 = %#x", crc);
                        crc_correct = (crc == ethernet_crc_frags(frame, 0,
                                                    frags_len(frame) - 4));
                } else {
                        crc_correct = false;
                        SIM_LOG_INFO(4, obj, 0, "too short frame");
                }
        } else {
                crc_correct = (crc_status == IEEE_802_15_4_Frame_CRC_Match);
        }

        if (!crc_correct) {
                SIM_LOG_INFO(4, obj, 0,
                             "drop the frame: data corruption detected");
                return IEEE_802_15_4_Transmit_Data_Corruption;
        }

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        if (ep->contention_ratio == 0) {
                to_transmit = true;
                SIM_LOG_INFO(4, obj, 0, "contention off");
        } else if (ep->contention_ratio == 100) {
                to_transmit = false;
                SIM_LOG_INFO(4, obj, 0, "channel always busy");
        } else {
                uint64 p;

                p = genrand_range(ep->random_state, 100);
                to_transmit = (p > ep->contention_ratio);

                SIM_LOG_INFO(4, obj, 0,
                             "contention (rand = %lld, contention_ratio = %d)",
                             p, ep->contention_ratio);
        }

        if (to_transmit) {
                size_t frame_len = frags_len(frame);
                uint8 frame_buf[frame_len];

                frags_extract(frame, frame_buf);

                HT_FOREACH_INT(&ep->rssi_table, it) {
                        uint64 tgt_ep_id;
                        uint32 rssi;

                        tgt_ep_id = ht_iter_int_key(it);
                        rssi = *((uint32 *)ht_iter_int_value(it));

                        if (rssi > 0) {
                                link_message_t *lm;

                                lm = new_ieee_802_15_4_message(frame_buf,
                                            frame_len, rssi, channel_page,
                                            channel_number, crc_status);

                                SIM_LOG_INFO(3, obj, 0,
                                             "send a message"
                                             " (tgt_ep_id = %#llx, rssi = %d)",
                                             tgt_ep_id, rssi);
                                SIMLINK_send_message(obj, tgt_ep_id, lm);
                        } else {
                                SIM_LOG_INFO(3, obj, 0,
                                             "no message sent"
                                             " (tgt_ep_id = %#llx, rssi = %d)",
                                             tgt_ep_id, rssi);
                        }
                }

                return IEEE_802_15_4_Transmit_No_Error;
        } else {
                return IEEE_802_15_4_Transmit_Channel_Contention;
        }
}

static void
set_rssi(conf_object_t *NOTNULL src_ep, uint64 tgt_ep_id, uint32 rssi)
{
        ieee_802_15_4_link_endpoint_t *ep;
        uint32 *rssi_p;

        ep = (ieee_802_15_4_link_endpoint_t *)src_ep;
        rssi_p = MM_MALLOC(1, uint32);
        *rssi_p = rssi;
        SIM_LOG_INFO(3, src_ep, 0,
                     "set RSSI (tgt_ep_id = %#llx, rssi = %d)",
                     tgt_ep_id, rssi);
        ht_update_int(&ep->rssi_table, tgt_ep_id, rssi_p);
}

static void
clear_all_rssi(conf_object_t *NOTNULL src_ep)
{
        ieee_802_15_4_link_endpoint_t *ep;

        SIM_LOG_INFO(3, src_ep, 0, "empty RSSI table");

        ep = (ieee_802_15_4_link_endpoint_t *)src_ep;
        ht_clear_int_table(&ep->rssi_table, true);
}

static void
remove_rssi(conf_object_t *NOTNULL src_ep, uint64 tgt_ep_id)
{
        ieee_802_15_4_link_endpoint_t *ep;
        uint32 *rssi_p;

        ep = (ieee_802_15_4_link_endpoint_t *)src_ep;
        rssi_p = (uint32 *)ht_lookup_int(&ep->rssi_table, tgt_ep_id);
        if (rssi_p == NULL) {
                SIM_LOG_INFO(2, src_ep, 0,
                             "RSSI (tgt_ep_id = %#llx) is not found",
                             tgt_ep_id);
                return;
        }

        SIM_LOG_INFO(3, src_ep, 0,
                     "remove RSSI (tgt_ep_id = %#llx)", tgt_ep_id);
        ht_remove_int(&ep->rssi_table, tgt_ep_id);
        MM_FREE(rssi_p);
}

static attr_value_t
get_node_table(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        int i = 0;
        attr_value_t lst;
        ieee_802_15_4_link_t *link;

        link = (ieee_802_15_4_link_t *)obj;
        lst = SIM_alloc_attr_list(ht_num_entries_str(&link->node_table));
        HT_FOREACH_STR(&link->node_table, it) {
                SIM_attr_list_set_item(&lst, i,
                        SIM_make_attr_list(2,
                                SIM_make_attr_string(ht_iter_str_key(it)),
                                SIM_make_attr_uint64(
                                        *((uint64 *)ht_iter_str_value(it)))));
                i++;
        }

        return lst;
}

static set_error_t
set_node_table(void *user_data, conf_object_t *obj,
               attr_value_t *val, attr_value_t *idx)
{
        ht_str_table_t new_table;
        ieee_802_15_4_link_t *link;

        link = (ieee_802_15_4_link_t *)obj;
        ht_init_str_table(&new_table, true);

        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                uint64 ep_id;
                uint64 *ep_id_p;
                attr_value_t v;
                const char *node_name;

                v = SIM_attr_list_item(*val, i);

                node_name = SIM_attr_string(SIM_attr_list_item(v, 0));

                ep_id = SIM_attr_integer(SIM_attr_list_item(v, 1));
                ep_id_p = MM_ZALLOC(1, uint64);
                *ep_id_p = ep_id;

                ht_insert_str(&new_table, node_name, ep_id_p);
        }

        ht_delete_str_table(&link->node_table, true);
        link->node_table = new_table;

        return Sim_Set_Ok;
}

static attr_value_t
get_rssi_table(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        int i = 0;
        attr_value_t lst;
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        lst = SIM_alloc_attr_list(ht_num_entries_int(&ep->rssi_table));
        HT_FOREACH_INT(&ep->rssi_table, it) {
                SIM_attr_list_set_item(&lst, i,
                        SIM_make_attr_list(2,
                                SIM_make_attr_uint64(ht_iter_int_key(it)),
                                SIM_make_attr_uint64(
                                        *((uint32 *)ht_iter_int_value(it)))));
                i++;
        }

        return lst;
}

static set_error_t
set_rssi_table(void *user_data, conf_object_t *obj,
               attr_value_t *val, attr_value_t *idx)
{
        ht_int_table_t new_table;
        ieee_802_15_4_link_endpoint_t *ep;
        uint64 ep_id;
        uint64 rssi;
        uint32 *rssi_p;
        attr_value_t v;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        ht_init_int_table(&new_table);

        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                v = SIM_attr_list_item(*val, i);

                ep_id = SIM_attr_integer(SIM_attr_list_item(v, 0));
                rssi = SIM_attr_integer(SIM_attr_list_item(v, 1));

                rssi_p = MM_MALLOC(1, uint32);
                *rssi_p = rssi;

                ht_insert_int(&new_table, ep_id, rssi_p);
        }

        ht_delete_int_table(&ep->rssi_table, true);
        ep->rssi_table = new_table;

        return Sim_Set_Ok;
}

static attr_value_t
get_rssi_always_drop(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        return SIM_make_attr_uint64(ep->rssi_always_drop);
}

static set_error_t
set_rssi_always_drop(void *user_data, conf_object_t *obj,
                     attr_value_t *val, attr_value_t *idx)
{
        int16 rssi_always_drop;

        rssi_always_drop = SIM_attr_integer(*val);

        if (rssi_always_drop < 0 || rssi_always_drop > 100) {
                SIM_LOG_INFO(1, obj, 0,
                        "The value range of rssi_always_drop is [0, 100].");

                return Sim_Set_Illegal_Value;
        } else {
                ieee_802_15_4_link_endpoint_t *ep;

                ep = (ieee_802_15_4_link_endpoint_t *)obj;
                ep->rssi_always_drop = rssi_always_drop;

                return Sim_Set_Ok;
        }
}

static attr_value_t
get_rssi_random_drop(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        return SIM_make_attr_uint64(ep->rssi_random_drop);
}

static set_error_t
set_rssi_random_drop(void *user_data, conf_object_t *obj,
                     attr_value_t *val, attr_value_t *idx)
{
        int16 rssi_random_drop;

        rssi_random_drop = SIM_attr_integer(*val);
        if (rssi_random_drop < 0 || rssi_random_drop > 100) {
                SIM_LOG_INFO(1, obj, 0,
                        "The value range of rssi_random_drop is [0, 100].");

                return Sim_Set_Illegal_Value;
        } else {
                ieee_802_15_4_link_endpoint_t *ep;

                ep = (ieee_802_15_4_link_endpoint_t *)obj;
                ep->rssi_random_drop = rssi_random_drop;

                return Sim_Set_Ok;
        }
}

static attr_value_t
get_rssi_random_drop_ratio(void *user_data, conf_object_t *obj,
                           attr_value_t *idx)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        return SIM_make_attr_uint64(ep->rssi_random_drop_ratio);
}

static set_error_t
set_rssi_random_drop_ratio(void *user_data, conf_object_t *obj,
                           attr_value_t *val, attr_value_t *idx)
{
        int16 rssi_random_drop_ratio;

        rssi_random_drop_ratio = SIM_attr_integer(*val);

        if (rssi_random_drop_ratio < 0 || rssi_random_drop_ratio > 100) {
                SIM_LOG_INFO(1, obj, 0,
                             "The value range of rssi_random_drop_ratio"
                             " is [0, 100].");

                return Sim_Set_Illegal_Value;
        } else {
                ieee_802_15_4_link_endpoint_t *ep;

                ep = (ieee_802_15_4_link_endpoint_t *)obj;
                ep->rssi_random_drop_ratio = rssi_random_drop_ratio;

                return Sim_Set_Ok;
        }
}

static attr_value_t
get_contention_ratio(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        return SIM_make_attr_uint64(ep->contention_ratio);
}

static set_error_t
set_contention_ratio(void *user_data, conf_object_t *obj,
                     attr_value_t *val, attr_value_t *idx)
{
        int16 contention_ratio;

        contention_ratio = SIM_attr_integer(*val);

        if (contention_ratio < 0 || contention_ratio > 100) {
                SIM_LOG_INFO(1, obj, 0,
                        "The value range of contention_ratio is [0, 100].");

                return Sim_Set_Illegal_Value;
        } else {
                ieee_802_15_4_link_endpoint_t *ep;

                ep = (ieee_802_15_4_link_endpoint_t *)obj;
                ep->contention_ratio = contention_ratio;

                return Sim_Set_Ok;
        }
}

static attr_value_t
get_random_state(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        bytes_t blob;
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        blob = genrand_serialization(ep->random_state);
        return SIM_make_attr_data_adopt(blob.len, (void *)blob.data);
}

static set_error_t
set_random_state(void *user_data, conf_object_t *obj,
                 attr_value_t *val, attr_value_t *idx)
{
        bytes_t b;
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        b.data = SIM_attr_data(*val);
        b.len = SIM_attr_data_size(*val);

        if (genrand_restore(ep->random_state, b))
                return Sim_Set_Ok;
        else
                return Sim_Set_Illegal_Value;
}

static conf_object_t *
ieee_802_15_4_link_endpoint_alloc_object(void *data)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = MM_ZALLOC(1, ieee_802_15_4_link_endpoint_t);
        return &ep->obj;
}

static void *
ieee_802_15_4_link_endpoint_init_object(conf_object_t *obj, void *data)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&ep->obj, false);
        ht_init_int_table(&ep->rssi_table);
        ep->random_state = genrand_init(0x12345678);

        return ep;
}

static void
ieee_802_15_4_link_endpoint_finalize_instance(conf_object_t *obj)
{
        SIMLINK_endpoint_finalize(obj);
}

static void
ieee_802_15_4_link_endpoint_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_endpoint_disconnect(obj);
}

static int
ieee_802_15_4_link_endpoint_delete_instance(conf_object_t *obj)
{
        ieee_802_15_4_link_endpoint_t *ep;

        ep = (ieee_802_15_4_link_endpoint_t *)obj;
        if (SIM_object_is_configured(obj))
                genrand_destroy(ep->random_state);

        ht_delete_int_table(&ep->rssi_table, true);
        MM_FREE(ep);
        return 0;
}

void
init_local()
{
        /* The link library must be initialized first. */
        SIMLINK_init_library();
        init_ethernet_crc_table();

        const class_data_t cl_methods = {
                .alloc_object = ieee_802_15_4_link_alloc_object,
                .init_object = ieee_802_15_4_link_init_object,
                .finalize_instance = ieee_802_15_4_link_finalize_instance,
                .pre_delete_instance = ieee_802_15_4_link_pre_delete_instance,
                .delete_instance = ieee_802_15_4_link_delete_instance,
                .class_desc = "model of IEEE 802.15.4 link",
                .description = "IEEE 802.15.4 link object" };
        conf_class_t *cl = SIM_register_class("ieee_802_15_4_link_impl",
                                              &cl_methods);

        /* Register the class for the link */
        SIMLINK_register_class(cl);

        SIM_register_typed_attribute(
                cl, "node_table",
                get_node_table, NULL,
                set_node_table, NULL,
                Sim_Attr_Optional,
                "[[s,i]*]", NULL,
                "translation table from node name to endpoint ID");

        const class_data_t epcl_methods = {
                .alloc_object = ieee_802_15_4_link_endpoint_alloc_object,
                .init_object = ieee_802_15_4_link_endpoint_init_object,
                .finalize_instance =
                        ieee_802_15_4_link_endpoint_finalize_instance,
                .pre_delete_instance =
                        ieee_802_15_4_link_endpoint_pre_delete_instance,
                .delete_instance = ieee_802_15_4_link_endpoint_delete_instance,
                .class_desc = "model of IEEE 802.15.4 link ednpoint",
                .description = "Endpoint for ieee_802_15_4_link objects." };
        conf_class_t *epcl = SIM_register_class("ieee_802_15_4_link_endpoint",
                                                &epcl_methods);

        SIM_register_typed_attribute(
                epcl, "rssi_table",
                get_rssi_table, NULL,
                set_rssi_table, NULL,
                Sim_Attr_Optional,
                "[[i,i]*]", NULL,
                "translation table from endpoint ID to RSSI value");
        SIM_register_typed_attribute(
                epcl, "rssi_always_drop",
                get_rssi_always_drop, NULL,
                set_rssi_always_drop, NULL,
                Sim_Attr_Optional,
                "i", NULL,
                "Messages taking an RSSI value lower than rssi_always_drop"
                " will always be dropped by the receiving endpoint.");
        SIM_register_typed_attribute(
                epcl, "rssi_random_drop",
                get_rssi_random_drop, NULL,
                set_rssi_random_drop, NULL,
                Sim_Attr_Optional,
                "i", NULL,
                "Messages taking an RSSI value higher than rssi_random_drop"
                " will always be delivered. Messages that take an RSSI value"
                " between rssi_always_drop and rssi_random_drop are dropped"
                " at a percentage of rssi_random_drop_ratio.");
        SIM_register_typed_attribute(
                epcl, "rssi_random_drop_ratio",
                get_rssi_random_drop_ratio, NULL,
                set_rssi_random_drop_ratio, NULL,
                Sim_Attr_Optional,
                "i", NULL,
                "Messages that take an RSSI value between rssi_always_drop"
                " and rssi_random_drop are dropped at a percentage of"
                " rssi_random_drop_ratio.");
        SIM_register_typed_attribute(
                epcl, "contention_ratio",
                get_contention_ratio, NULL,
                set_contention_ratio, NULL,
                Sim_Attr_Optional,
                "i", NULL,
                "The potential maximum demand to the bandwidth. The higher"
                " the contention ratio, the lower the effective bandwidth"
                " offered.");
        SIM_register_typed_attribute(
                epcl, "random_state",
                get_random_state, NULL,
                set_random_state, NULL,
                Sim_Attr_Optional | Sim_Attr_Internal,
                "d", NULL,
                "The state of repeatable pseudo random number generator.");

        static const ieee_802_15_4_link_interface_t
                ieee_802_15_4_link_if = { .transmit = transmit };
        SIM_register_interface(epcl, "ieee_802_15_4_link",
                               &ieee_802_15_4_link_if);

        static const ieee_802_15_4_control_interface_t
        ieee_802_15_4_control_if = { .set_rssi = set_rssi,
                                     .remove_rssi = remove_rssi,
                                     .clear_all_rssi = clear_all_rssi };
        SIM_register_interface(epcl, "ieee_802_15_4_control",
                               &ieee_802_15_4_control_if);

        /* Register the class for endpoints */
        SIMLINK_register_endpoint_class(epcl, "[diiii]");
}
