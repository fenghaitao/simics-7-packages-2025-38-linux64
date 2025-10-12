/*
  x86-reset-bus.c

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <simics/device-api.h>
#include <simics/arch/x86.h>
#include <simics/model-iface/cpu-group.h>
#include <simics/model-iface/processor-info.h>
#include <simics/devs/signal.h>
#include <simics/simulator/conf-object.h>

#include "x86-reset-bus.h"

typedef struct irq_device {
        conf_object_t obj;
        cpu_list_t reset_tgts;
        VECT(const x86_interface_t *) x86_iface;
        const a20_interface_t *a20_iface;
} irq_device_t;

static irq_device_t *
from_obj(conf_object_t *obj)
{
        return (irq_device_t *)obj;
}

static conf_object_t *
to_obj(irq_device_t *con)
{
        return &con->obj;
}

static conf_object_t *
alloc(conf_class_t *cls)
{
        irq_device_t *irq = MM_ZALLOC(1, irq_device_t);
        VINIT(irq->reset_tgts);
        VINIT(irq->x86_iface);
        return to_obj(irq);
}

static void
dealloc(conf_object_t *obj)
{
        irq_device_t *irq = from_obj(obj);
        VFREE(irq->reset_tgts);
        VFREE(irq->x86_iface);
        MM_FREE(irq);
}

/* Exported through the cpu-group interface */
static const cpu_list_t *
get_cpu_list(conf_object_t *obj)
{
        irq_device_t *irq = from_obj(obj);
        return &irq->reset_tgts;
}

static void
set_a20_line(conf_object_t *obj, int value)
{
	irq_device_t *irq = from_obj(obj);

        if (VLEN(irq->reset_tgts) > 0)
                irq->a20_iface->set_a20_line(VGET(irq->reset_tgts, 0), value);
}

static int
get_a20_line(conf_object_t *obj)
{
	irq_device_t *irq = from_obj(obj);

        if (VLEN(irq->reset_tgts) > 0)
                return irq->a20_iface->get_a20_line(VGET(irq->reset_tgts, 0));
        return 0;
}

static void
reset_all(conf_object_t *obj)
{
        irq_device_t *irq = from_obj(obj);

        VFORI(irq->reset_tgts, i) {
                VGET(irq->x86_iface, i)->set_pin_status(
                        VGET(irq->reset_tgts, i), Pin_Init, 1);
        }
}

/* send #RESET to processors instead of INIT */
static void
assert_reset_callback(conf_object_t *obj, void *param)
{
        const signal_interface_t* ireset = SIM_C_GET_PORT_INTERFACE(
                obj, signal, "RESET");

        if (ireset) {
                ireset->signal_raise(obj);
                ireset->signal_lower(obj);
        }
}

/* disables CPU */
static void
disable_cpu(conf_object_t *cpu)
{
    if (!SIM_object_is_configured(cpu))
            SIM_require_object(cpu);

    const x86_reg_access_interface_t *iface =
            SIM_C_GET_INTERFACE(cpu, x86_reg_access);
    if (iface)
            iface->set_activity_state(cpu, X86_Activity_Shutdown);
}

static void
assert_reset(conf_object_t *obj, int type)
{
        irq_device_t *irq = from_obj(obj);

        VFORI(irq->reset_tgts, i) {
                SIM_run_unrestricted(VGET(irq->reset_tgts, i),
                                     assert_reset_callback, NULL);
        }
}

static void
disable_cpus(conf_object_t *obj)
{
        irq_device_t *irq = from_obj(obj);

        VFORI(irq->reset_tgts, i) {
                disable_cpu(VGET(irq->reset_tgts, i));
        }
}

static void
_enable_cpu(conf_object_t *cpu)
{
    SIM_object_is_configured(cpu);

    /* The code is here is a bit fishy, but is needed to use this class
       instead of the stc-x86-reset-bus class in the VP repo. This is on its
       way out but still required.
       https://github.com/intel-restricted/applications.simulators.isim.vp/commit/333d7dc0128dfeb8e16b88b6620d327122ac67e4
    */

    attr_value_t apic_attr = SIM_get_attribute(cpu, "apic");
    conf_object_t *apic = SIM_attr_object(apic_attr);
    attr_value_t cpuid_physical_apic_id = SIM_get_attribute(
            cpu, "cpuid_physical_apic_id");

    const x86_reg_access_interface_t *regs = SIM_C_GET_INTERFACE(
            cpu, x86_reg_access);
    regs->set_activity_state(cpu, X86_Activity_Normal);

    /* It is also required to set the APIC bsp to 0. */
    const apic_cpu_interface_t *apic_iface = SIM_C_GET_INTERFACE(
            apic, apic_cpu);
    if (apic_iface)
            apic_iface->power_on(apic, true,
                                 SIM_attr_integer(cpuid_physical_apic_id));

    const processor_info_v2_interface_t*cpu_iface = SIM_C_GET_INTERFACE(
            cpu, processor_info_v2);
    if (cpu_iface)
            cpu_iface->enable_processor(cpu);
}

static void
enable_cpu(conf_object_t *obj, int value)
{
    irq_device_t *irq = from_obj(obj);

    if (VLEN(irq->reset_tgts) > value) {
            _enable_cpu(VGET(irq->reset_tgts, value));
    }
}

static set_error_t
set_reset_tgts(conf_object_t *obj, attr_value_t *val)
{
	irq_device_t *irq = from_obj(obj);

        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                if (!SIM_C_GET_INTERFACE(
                            SIM_attr_object(SIM_attr_list_item(*val, i)),
                            x86)) {
                        return Sim_Set_Interface_Not_Found;
                }
                if (i == 0) {
                        if (!SIM_C_GET_INTERFACE(
                                    SIM_attr_object(SIM_attr_list_item(
                                                            *val, i)), a20)) {
                                return Sim_Set_Interface_Not_Found;
                        }
                }
        }

        VFREE(irq->reset_tgts);
        VFREE(irq->x86_iface);

        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                conf_object_t *c = SIM_attr_object(SIM_attr_list_item(*val, i));
                VADD(irq->reset_tgts, c);
                VADD(irq->x86_iface, SIM_C_GET_INTERFACE(c, x86));
        }
        irq->a20_iface = NULL;
        if (!VEMPTY(irq->reset_tgts)) {
                irq->a20_iface = SIM_C_GET_INTERFACE(
                        VGET(irq->reset_tgts, 0), a20);
        }
        return Sim_Set_Ok;
}

static attr_value_t
get_reset_tgts(conf_object_t *obj)
{
	irq_device_t *irq = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(VLEN(irq->reset_tgts));
        for (int i = 0; i < VLEN(irq->reset_tgts); i++)
                SIM_attr_list_set_item(
                        &ret, i,
                        SIM_make_attr_object(VGET(irq->reset_tgts, i)));
        return ret;
}

static void
reset_all_signal_raise(conf_object_t *obj)
{
	reset_all(obj);
}

static void
reset_all_signal_lower(conf_object_t *obj)
{
	/* do nothing */
}

static void
port_reset_all_signal_raise(conf_object_t *pobj)
{
	reset_all_signal_raise(SIM_port_object_parent(pobj));
}

static void
port_reset_all_signal_lower(conf_object_t *pobj)
{
	reset_all_signal_lower(SIM_port_object_parent(pobj));
}

void
init_local()
{
        class_info_t funcs = {
                .alloc = alloc,
                .dealloc = dealloc,
                .short_desc = "forwards resets to processors",
                .description =
		"The " DEVICE_NAME " device forwards resets"
                " to connected x86 processors."
        };
        conf_class_t *class = SIM_create_class(DEVICE_NAME, &funcs);

        static const x86_reset_bus_interface_t xrbi = {
                .set_a20_line = set_a20_line,
                .get_a20_line = get_a20_line,
                .reset_all = reset_all,
                .assert_reset = assert_reset,
                .disable_cpus = disable_cpus,
                .enable_cpu   = enable_cpu,
        };
        SIM_REGISTER_INTERFACE(class, x86_reset_bus, &xrbi);

        static const cpu_group_interface_t cgi = {
                .get_cpu_list = get_cpu_list,
        };
        SIM_REGISTER_INTERFACE(class, cpu_group, &cgi);

        SIM_register_attribute(
                class, "reset_targets",
                get_reset_tgts,
                set_reset_tgts,
                Sim_Attr_Optional, "[o*]",
                "A list of objects implementing the <tt>" X86_INTERFACE
                "</tt> and <tt>" A20_INTERFACE "</tt> interfaces.");

        SIM_register_attribute(
                class, "cpu_list",
                get_reset_tgts,
                NULL,
                Sim_Attr_Pseudo, "[o*]",
                "List of all connected processors. This attribute is "
                "available in all classes implementing the \""
                CPU_GROUP_INTERFACE "\" interface.");

        conf_class_t *signal_cls = SIM_register_simple_port(
                class, "port.reset_all", "Resets all connected processors");
        static const signal_interface_t port_sigifc = {
                .signal_raise = port_reset_all_signal_raise,
                .signal_lower = port_reset_all_signal_lower
        };
        SIM_REGISTER_INTERFACE(signal_cls, signal, &port_sigifc);

        static const signal_interface_t sigifc = {
                .signal_raise = reset_all_signal_raise,
                .signal_lower = reset_all_signal_lower
        };
        SIM_REGISTER_PORT_INTERFACE(
                class, signal, &sigifc,
                "reset_all", "Resets all connected processors");
}
