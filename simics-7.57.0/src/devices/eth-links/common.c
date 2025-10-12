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

#include <simics/device-api.h>
#include <simics/devs/ethernet.h>
#include <simics/simulator/conf-object.h>
#include <simics/simulator-api.h>

// TODO: This violates the Device API (but works with Model Builder currently)
#include <simics/simulator/oec-control.h>

#include "crc.h"
#include "common.h"

static conf_class_t *snoop_ep_cls; /* snoop link endpoint class */

void
link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

void
ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        common_link_endpoint_t *cep = (common_link_endpoint_t *)ep;
        const ethernet_common_interface_t *common_iface =
                SIM_c_get_port_interface(
                        SIMLINK_endpoint_device(ep),
                        ETHERNET_COMMON_INTERFACE,
                        SIMLINK_endpoint_port(ep));
        if (!common_iface) {
                uint8 name[1024];
                buffer_t scratch = { .data = name,
                                     .len = sizeof(name) };
                SIM_LOG_ERROR(ep, 0, "The device '%s' does not "
                              "implement the ethernet_common interface."
                              " In other words, it is not compatible "
                              "with the new eth-links module.",
                              SIMLINK_endpoint_dev_name(ep, scratch));
        }
        cep->ifc = common_iface;
}

void
ep_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

typedef struct {
        common_link_endpoint_t cep;
        ethernet_link_snoop_t snoop_fun;
        lang_void *user_data;
} snoop_ep_t;

void
attach_snoop_helper(common_link_t *clink, conf_object_t *clock)
{
        ASSERT_OUTSIDE_EXECUTION_CONTEXT();
        ASSERT(SIM_object_is_configured(&clink->obj));
        SIM_LOG_INFO(3, &clink->obj, 0, "attach snoop (clock: %s)",
                     clock ? SIM_object_name(clock) : "(no clock)");
}

/* <add id="eth_attach_snoop"><insert-upto text="}"/></add> */
static conf_object_t *
default_attach_snoop(conf_object_t *obj, conf_object_t *clock,
                     ethernet_link_snoop_t snoop_fun, lang_void *user_data)
{
        common_link_t *clink = (common_link_t *)obj;
        attach_snoop_helper(clink, clock);
        attr_value_t attrs = SIM_make_attr_list(0);
        snoop_ep_t *snoop = (snoop_ep_t *)SIMLINK_snoop_endpoint_create(
                snoop_ep_cls, &clink->obj, clock, attrs);
        SIM_attr_free(&attrs);
        snoop->snoop_fun = snoop_fun;
        snoop->user_data = user_data;
        return &snoop->cep.obj;
}

FORCE_INLINE common_link_endpoint_t *
common_link_ep(const conf_object_t *ep)
{
        return (common_link_endpoint_t *)ep;
}

void
deliver_to_snoop(ethernet_link_snoop_t snoop_fun, lang_void *snoop_data,
                 conf_object_t *clock, const frags_t *frame,
                 eth_frame_crc_status_t crc_status)
{
        if (crc_status == Eth_Frame_CRC_Match
            && frags_len(frame) >= 4) {
                size_t dlen = frags_len(frame) - 4;
                uint32 crc = ethernet_crc_frags(frame, 0, dlen);
                STORE_LE32(&crc, crc);
                frags_t fixed_frame;
                frags_init_add_from_frags(&fixed_frame, frame, 0, dlen);
                frags_add(&fixed_frame, &crc, sizeof(crc));
                snoop_fun(snoop_data, clock, &fixed_frame,
                                 crc_status);
        } else {
                snoop_fun(snoop_data, clock, frame, crc_status);
        }
}

void
deliver_frame(conf_object_t *ep, const frags_t *frame, bool crc_correct)
{
        eth_frame_crc_status_t crc_status = 
                crc_correct ? Eth_Frame_CRC_Match : Eth_Frame_CRC_Mismatch;
        if (SIMLINK_endpoint_is_device(ep)) {
                common_link_ep(ep)->ifc->frame(SIMLINK_endpoint_device(ep), frame,
                                               crc_status);
        } else {
                snoop_ep_t *snoop = (snoop_ep_t *)ep;
                deliver_to_snoop(snoop->snoop_fun, snoop->user_data,
                                 SIMLINK_endpoint_clock(ep), frame,
                                 crc_status);
        }
}

bool
check_crc(const frags_t *frame)
{
        uint32 crc = get_ethernet_crc_frags(frame);
        return crc == ethernet_crc_frags(frame, 0, frags_len(frame) - 4);
}

void
broadcast_frame(conf_object_t *ep, const frags_t *frame, 
                eth_frame_crc_status_t crc_status)
{
        common_link_endpoint_t *cep = (common_link_endpoint_t *)ep;
        SIM_LOG_INFO(3, &cep->obj, 0, "broadcast_frame: %zu bytes",
                     frags_len(frame));

        common_link_t *clink = (common_link_t *)SIMLINK_endpoint_link(ep);

        /* Transform CRC_Unknown into either Match or Mismatch */
        bool crc_correct = crc_status == Eth_Frame_CRC_Unknown
                ? check_crc(frame)
                : (crc_status == Eth_Frame_CRC_Match);
        link_message_t *msg = clink->eth_funcs->new_frame_message(
                frags_len(frame), frags_extract_alloc(frame), crc_correct);

        SIMLINK_send_message(ep, LINK_BROADCAST_ID, msg);
}

void
register_ethernet_common_link_interfaces(
        conf_class_t *cls,
        conf_object_t *(*attach_snoop)(
                conf_object_t *obj, conf_object_t *clock,
                ethernet_link_snoop_t snoop_fun, lang_void *user_data))
{
        ethernet_snoop_interface_t *ifc =
                MM_MALLOC(1, ethernet_snoop_interface_t);
        ifc->attach = attach_snoop ? attach_snoop : default_attach_snoop;
        SIM_register_interface(cls, ETHERNET_SNOOP_INTERFACE, ifc);
}

void
common_pre_delete_instance(conf_object_t *link)
{
        SIMLINK_pre_delete(link);
}

int
common_delete_instance(conf_object_t *link)
{
        MM_FREE(link);
        return 0;
}

void
register_ethernet_common_ep_interfaces(
        conf_class_t *cls, void (*frame)(conf_object_t *, const frags_t *,
                                         eth_frame_crc_status_t crc_status))
{
        ethernet_common_interface_t *common_ifc =
                MM_MALLOC(1, ethernet_common_interface_t);
        common_ifc->frame = frame;
        SIM_register_interface(cls, ETHERNET_COMMON_INTERFACE, common_ifc);
}

void
common_eth_link_init(
        common_link_t *clink,
        const link_type_t *link_type, const eth_funcs_t *eth_funcs)
{
        SIMLINK_init(&clink->obj, link_type);
        clink->eth_funcs = eth_funcs;
}

void
common_eth_ep_constructor(common_link_endpoint_t *cep, bool snoop)
{
        SIMLINK_endpoint_init(&cep->obj, snoop);
}

void
common_eth_ep_destructor(common_link_endpoint_t *cep)
{
        SIMLINK_endpoint_disconnect(&cep->obj);
}

conf_object_t *
get_link_from_ep(conf_object_t *ep)
{
        return SIMLINK_endpoint_link(ep);
}

static conf_object_t *
snoop_ep_alloc_object(void *data)
{
        snoop_ep_t *snoop = MM_ZALLOC(1, snoop_ep_t);
        return &snoop->cep.obj;
}

static void *
snoop_ep_init_object(conf_object_t *obj, void *data)
{
        snoop_ep_t *snoop = (snoop_ep_t *)obj;
        common_eth_ep_constructor(&snoop->cep, true);
        return snoop;
}

static void
snoop_ep_pre_delete_instance(conf_object_t *obj)
{
        snoop_ep_t *snoop = (snoop_ep_t *)obj;
        common_eth_ep_destructor(&snoop->cep);
}

static int
snoop_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return is ignored */
}

#define ETH_DST_OFFSET  0
#define ETH_SRC_OFFSET  6
#define ETH_TYPE_OFFSET 12
#define DATA_FRAME_LENGTH 38

typedef enum {src = 1, dst = 2, type = 4} combo_t;

static bool
check_matching_criteria(net_bp_data_t *bpd, const uint8 *frame)
{
        if (bpd->combinations & src) {
                if (memcmp(bpd->src_mac,
                           frame + ETH_SRC_OFFSET, 6) != 0)
                        return false;
        }
        if (bpd->combinations & dst) {
                if (memcmp(bpd->dst_mac,
                           frame + ETH_DST_OFFSET, 6) != 0)
                        return false;
        }
        if (bpd->combinations & type) {
                if (memcmp(bpd->eth_type, frame + ETH_TYPE_OFFSET, 2) != 0)
                        return false;
        }
        return true;
}

static void
chk_frame(lang_void *user_data,
               conf_object_t *clock,
               const frags_t *packet,
               eth_frame_crc_status_t crc_status)
{
        net_bp_data_t *bpd = (net_bp_data_t*)user_data;
        uint8 buf[DATA_FRAME_LENGTH];
        bytes_t bd;
        bd.data = buf;
        bd.len = DATA_FRAME_LENGTH;
        const frags_frag_t * stream = packet->fraglist;
        for (int i  = 0; i < packet->nfrags; i++, stream++) {
                if (check_matching_criteria(bpd, stream->start)) {
                        memcpy(buf, stream->start, DATA_FRAME_LENGTH);
                        bpd->cb(bpd->obj, bd, DATA_FRAME_LENGTH,
                                bpd->bp_id);
                }
        }
}

static net_breakpoints_t *
init_net_breakpoints(conf_object_t *obj, common_link_t *cl, int log_group)
{
        if (cl->bpds)
                return cl->bpds;
        cl->bpds = MM_ZALLOC(1, net_breakpoints_t);
        if (!cl->bpds)
                return NULL;
        cl->bpds->obj = obj;
        cl->bpds->log_group = log_group;
        VINIT(cl->bpds->break_triggers);
        return cl->bpds;
}

int64 bp_add(conf_object_t *obj, bytes_t src_mac, bytes_t dst_mac,
             int eth_type, break_net_cb_t cb, common_link_t *cl, int64 bp_id,
             bool once)
{
        net_bp_data_t *bpd;
        net_breakpoints_t *bpds = init_net_breakpoints(obj, cl, 4);
        if (!bpds)
                return 0;

        bpd = MM_MALLOC(1, net_bp_data_t);
        if (!bpd)
                return 0;

        bpd->combinations = 0;

        if (src_mac.len) {
                memcpy(bpd->src_mac ,src_mac.data, src_mac.len);
                bpd->combinations = src;
        }
        if (dst_mac.len) {
                memcpy(bpd->dst_mac, dst_mac.data, dst_mac.len);
                bpd->combinations |= dst;
        }
        if (eth_type)
                bpd->combinations |= type;
        if (!bpd->combinations)
                return 0;

        bpd->obj = obj;
        bpd->cb  = cb;
        bpd->bp_id = bp_id;
        bpd->once = once;
        bpd->eth_type[0] = eth_type >> 8;
        bpd->eth_type[1] = eth_type & 0xff;
        const ethernet_snoop_interface_t * iface =
                SIM_C_GET_INTERFACE(obj, ethernet_snoop);
        bpd->snoop = iface->attach(obj, NULL, chk_frame, bpd);
        VADD(bpds->break_triggers, bpd);

        return bpd->bp_id;
}

static void
remove_one_bp(lang_void *NOTNULL param)
{
        net_bp_data_t *bpd = (net_bp_data_t *)param;
        SIM_delete_object(bpd->snoop);
        MM_FREE(bpd);
}

void bp_remove(conf_object_t *obj, common_link_t *link, int64 bp_id)
{
        net_breakpoints_t *bpds = link->bpds;
        VFORP(bpds->break_triggers, net_bp_data_t, bpd) {
                if (bpd->bp_id == bp_id) {
                        SIM_run_alone(remove_one_bp, bpd);
                }
        }
}

void tear_down_network_breakpoints(common_link_t *cl)
{
        net_breakpoints_t *bpds = cl->bpds;
        if (bpds) {
                VFORP(bpds->break_triggers, net_bp_data_t, bpd) {
                        SIM_run_alone(remove_one_bp, bpd);
                }
                VFREE(bpds->break_triggers);
        }
}

void init_eth_hub_link();
void init_eth_cable_link();
void init_eth_switch_link();

/* <add id="eth_init"><insert-until text="// eth_init_end"/></add> */
void
init_local()
{
        SIMLINK_init_library();
        init_eth_hub_link();
        init_eth_cable_link();
        init_eth_switch_link();
	init_ethernet_crc_table();

        const class_data_t snoop_ep_cls_funcs = {
                .alloc_object = snoop_ep_alloc_object,
                .init_object = snoop_ep_init_object,
                .finalize_instance = ep_finalize_instance,
                .pre_delete_instance = snoop_ep_pre_delete_instance,
                .delete_instance = snoop_ep_delete_instance,
                .description = "Ethernet link snoop endpoint",
                .class_desc = "an Ethernet link snoop endpoint",
                .kind = Sim_Class_Kind_Pseudo,
        };
        snoop_ep_cls = SIM_register_class("eth-link-snoop-endpoint",
                                          &snoop_ep_cls_funcs);
        SIMLINK_register_snoop_endpoint_class(snoop_ep_cls);
}
// eth_init_end <- jdocu insert-until marker
