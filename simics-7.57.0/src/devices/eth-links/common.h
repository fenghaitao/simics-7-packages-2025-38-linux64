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

#ifndef COMMON_H
#define COMMON_H

#include <simics/devs/ethernet.h>
#include <simics/devs/liblink.h>
#include <simics/util/inet.h>

typedef struct net_bp_data
{
        bool active;
        bool once;
        int64 bp_id;
        conf_object_t * snoop;
        uint8 src_mac[6];
        uint8 dst_mac[6];
        uint8 eth_type[2];
        uint8 combinations;
        conf_object_t *obj;
        break_net_cb_t cb;
} net_bp_data_t;

typedef struct eth_breakpoints {
        conf_object_t *obj;
        int log_group;
        int64 next_id;
        VECT(net_bp_data_t*) break_triggers;
} net_breakpoints_t;

typedef struct {
        conf_object_t obj;
        const ethernet_common_interface_t *ifc;
} common_link_endpoint_t;

/* Link-type specific functions called by code in common.c. */
typedef struct {
        link_message_t *(*new_frame_message)(size_t len, const void *data,
                                             bool crc_correct);
} eth_funcs_t;

typedef struct {
        conf_object_t obj;
        const eth_funcs_t *eth_funcs;
        net_breakpoints_t *bpds;
} common_link_t;

#define CMP(a, b) ((a) < (b) ? -1 : (a) == (b) ? 0 : 1)

attr_value_t endpoint_info_to_attr(const conf_object_t *ep);
void *endpoint_info_from_attr(conf_object_t *link, attr_value_t state);
void free_endpoint_info(conf_object_t *ep);
void finalize_endpoint_info_common(conf_object_t *ep);
void link_finalize_instance(conf_object_t *obj);
void ep_device_changed(conf_object_t *obj, conf_object_t *old_dev);
void ep_finalize_instance(conf_object_t *obj);
void attach_snoop_helper(common_link_t *clink, conf_object_t *clock);
void deliver_frame(conf_object_t *ep, const frags_t *frame, bool crc_correct);
bool check_crc(const frags_t *frame);
void broadcast_frame(conf_object_t *obj, const frags_t *frame,
                     eth_frame_crc_status_t crc_status);
void register_ethernet_common_link_interfaces(
        conf_class_t *cls,
        conf_object_t *(*attach_snoop)(
                conf_object_t *obj, conf_object_t *clock,
                ethernet_link_snoop_t snoop_fun, lang_void *user_data));
void register_ethernet_common_ep_interfaces(
        conf_class_t *cls, void (*frame)(conf_object_t *, const frags_t *,
                                         eth_frame_crc_status_t crc_status));
void common_eth_link_init(
        common_link_t *clink,
        const link_type_t *link_type, const eth_funcs_t *eth_funcs);
void common_pre_delete_instance(conf_object_t *link);
int common_delete_instance(conf_object_t *link);
void common_eth_ep_constructor(common_link_endpoint_t *cep, bool snoop);
void common_eth_ep_destructor(common_link_endpoint_t *cep);
conf_object_t *get_link_from_ep(conf_object_t *ep_obj);
void deliver_to_snoop(ethernet_link_snoop_t snoop_fun, lang_void *data,
                      conf_object_t *clock, const frags_t *frame,
                      eth_frame_crc_status_t crc_status);
int64 bp_add(conf_object_t *obj, bytes_t src_mac, bytes_t dst_mac,
             int eth_type, break_net_cb_t cb,
             common_link_t *cl, int64 bp_id, bool once);
void bp_remove(conf_object_t *obj, common_link_t *link, int64 bp_id);
void tear_down_network_breakpoints(common_link_t *cl);
#endif /* COMMON_H */
