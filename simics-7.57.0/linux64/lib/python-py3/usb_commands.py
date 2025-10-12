# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli

def get_usb_uhci_info(obj):
    return []

def get_usb_ehci_info(obj):
    return []

def get_usb_uhci_status(obj):
    devs = []
    dev_list = obj.usb_devices
    for p in range(len(dev_list)):
        devs += [("port[%d]" % p, dev_list[p])]
    return [("Connected USB devices", devs)]

def get_usb_ehci_status(obj):
    devs = []
    dev_list = obj.usb_devices
    for p in range(len(dev_list)):
        devs += [("port[%d]" % p, dev_list[p])]
    cmps = []
    cmp_list = obj.companion_hc
    for p in range(len(cmp_list)):
        cmps += [("port[%d]" % p, cmp_list[p])]
    return [("Connected USB devices", devs),
            ("Companion host controllers", cmps)]

def print_usb_ehci_descriptors_cmd(obj):
    def read_mem(obj, addr, size):
        mem = obj.pci_bus.memory_space
        return mem.iface.memory_space.read(obj, addr, size, 1)

    def get_addr(obj, addr):
        if obj.usb_regs_hccparams & 1:
            return obj.usb_regs_ctrldssegment << 32 | addr
        else:
            return addr

    class QH:
        def __init__(self, obj, addr):
            self.obj = obj
            self.addr = addr
            self.setup()

        def setup(self):
            # 64 bit or 32 bit
            if self.obj.usb_regs_hccparams & 1:
                size = 17 * 4
            else:
                size = 12 * 4
            data = read_mem(self.obj, self.addr, size)
            self.link_ptr = (data[0x3] << 24 |
                             data[0x2] << 16 |
                             data[0x1] << 8 |
                             data[0x0] & 0xf0)
            self.typ = data[0x0] >> 1 & 0x3
            self.terminate = data[0x0] & 1
            self.dev_addr = data[4] & 0x7f
            self._next = (data[0x13] << 24 |
                          data[0x12] << 16 |
                          data[0x11] << 8 |
                          data[0x10] & 0xe0)
            self.next_t = data[0x10] & 1

        def get_info(self):
            s  = " + QH at 0x%016x:\n" % self.addr
            s += "      link ptr: 0x%016x\n" % self.link_ptr
            s += "      terminate: %d\n" % self.terminate
            s += "      device address: 0x%x\n" % self.dev_addr
            s += "      next ptr: 0x%016x\n" % self._next
            s += "      next t: %d\n" % self.next_t
            return s

    class QTD:
        def __init__(self, obj, addr):
            self.obj = obj
            self.addr = addr
            self.setup()

        def setup(self):
            # 64 bit or 32 bit
            if self.obj.usb_regs_hccparams & 1:
                size = 13 * 4
            else:
                size = 8 * 4
            data = read_mem(self.obj, self.addr, size)
            self._next = (data[0x3] << 24 |
                          data[0x2] << 16 |
                          data[0x1] << 8 |
                          data[0x0] & 0xe0)
            self.next_t = data[0x0] & 1

        def get_info(self):
            s  = "    + qTD at 0x%016x:\n" % self.addr
            s += "         next ptr: 0x%016x\n" % self._next
            s += "         next t: %d\n" % self.next_t
            return s

    if not (obj.usb_regs_usbcmd & 0x1):
        print("Asynchronous list descriptors not enabled.")
        return
    s = "Asynchronous List Descriptors\n"
    addr = get_addr(obj, obj.usb_regs_asynclistaddr)
    start = addr
    while True:
        qh = QH(obj, addr)
        s += qh.get_info()

        qtd_addr = qh._next
        qtd_t = qh.next_t
        while not qtd_t:
            qtd = QTD(obj, qtd_addr)
            s += qtd.get_info()
            qtd_addr = qtd._next
            qtd_t = qtd.next_t

        # break if we have no more QHs in list
        if qh.terminate:
            break
        addr = qh.link_ptr
        # break if we have reached start QH
        if start == addr:
            break
    print(s)

def register_usb_ehci_descriptors_command(cls):
    cli.new_command("print-descriptors", print_usb_ehci_descriptors_cmd,
            [],
            type  = ["USB"],
            short = "print descriptors",
            cls = cls,
            doc = """Print the USB EHCI descriptors.""")
