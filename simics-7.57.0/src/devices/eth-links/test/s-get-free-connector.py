# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test that get-free-connector commands work as expected

SIM_create_object("clock", "clock0", freq_mhz=1)

SIM_load_module("eth-links")
SIM_load_module("service-node")

# we want stacktraces if a command fails
def cmd(x):
    try:
        return run_command(x)
    except CliError as msg:
        raise Exception("Failed running '%s': %s" % (x, msg))

def cmd_expect_fail(x):
    try:
        run_command(x)
    except CliError:
        return
    raise Exception("command %s should fail but did not" % x)

class Builder:
    next_ep = 0             # next endpoint
    next_switch = 0         # next switch number
    connections = []

    free_eps = []
    do_instantiate = False

    def __init__(self):
        cmd("create-service-node-comp snd")
        self.instantiate()

    def get_ep(self):
        if self.free_eps:
            return self.free_eps.pop()
        cmd("snd.add-connector 192.168.0.%d" % self.next_ep)
        ret = "snd.connector_link%d" % self.next_ep
        self.next_ep += 1
        return ret

    def make_switch(self, switch):
        cmd("create-%s sw%d" % (switch, self.next_switch))
        self.instantiate()
        obj = SIM_get_object("sw%d" % self.next_switch)
        self.next_switch += 1
        return obj

    def make_vlan_switch(self, id_list):
        obj = self.make_switch("ethernet-vlan-switch")
        for x in id_list:
            cmd("%s.add-vlan %d" % (obj.name, x))
        return obj

    def instantiate(self):
        if self.do_instantiate:
            cmd("instantiate-components")

    def connect(self, c1, c2):
        cmd("connect %s %s" % (c1, c2))
        self.connections.append((c1, c2))

    def disconnect(self, ind):
        (c1, c2) = self.connections[ind]
        del self.connections[ind]
        cmd("disconnect %s %s" % (c1, c2))
        for x in (c1, c2):
            if "snd.connector_link" in x:
                self.free_eps.append(x)

    def disconnect_all(self):
        while self.connections:
            self.disconnect(0)

def test_get_free_connector(switch):
    name = builder.make_switch(switch).name
    def connect():
        connector = cmd("%s.get-free-connector" % name)
        builder.connect(builder.get_ep(), connector)

    connect()
    connect()
    builder.disconnect(-2)
    connect()
    builder.disconnect(-1)
    builder.disconnect(-1)
    connect()
    connect()

    if switch == "ethernet-cable":
        cmd_expect_fail("%s.get-free-connector" % name)
    builder.disconnect_all()
    print("test-%s%s: OK" % (switch, "-inst" if builder.do_instantiate else ""))

def test_get_free_vlan_connector():
    name = builder.make_vlan_switch([3, 5]).name

    def connect(vlan_id, is_trunk):
        if is_trunk:
            s = "get-free-trunk-connector"
        else:
            s = "get-free-connector"
        connector = cmd("%s.%s %s" % (name, s, vlan_id))
        builder.connect(builder.get_ep(), connector)

    for trunk in [False, True]:
        for vlan_id in [3, 5]:
            connect(vlan_id, trunk)
            connect("vlan_id = %d" % vlan_id, trunk)
            builder.disconnect(-2)
            connect(vlan_id, trunk)
            builder.disconnect(-1)
            builder.disconnect(-1)
            connect(vlan_id, trunk)
            connect(vlan_id, trunk)

    builder.disconnect_all()
    print("test-vlan%s: OK" % ("-inst" if builder.do_instantiate else ""))

def test_many_devices():
    name = builder.make_vlan_switch([1]).name
    for x in range(20):
        connector = cmd("%s.get-free-connector vlan_id = 1" % name)
        builder.connect(builder.get_ep(), connector)
    builder.disconnect_all()
    print(("test-many-devices%s: OK"
           % ("-inst" if builder.do_instantiate else "")))


builder = Builder()

for x in [False, True]:
    builder.do_instantiate = x
    test_get_free_connector("ethernet-switch")
    test_get_free_connector("ethernet-hub")
    test_get_free_connector("ethernet-cable")
    test_get_free_vlan_connector()
    test_many_devices()

print("s-get-free-connector: all tests passed")
