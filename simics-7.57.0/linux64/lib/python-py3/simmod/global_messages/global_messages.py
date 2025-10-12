# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import ast
import simics

class Global_msg:
    def init(self, tag):
        self.tag = tag
        msg_handlers[tag] = self
        self.count = 0
    def handle_msg(self, arg):
        self.count += 1
        self.receive(arg)
    def receive(self, arg):
        pass
    def cond(self):
        return self.count > 0
    def wait(self):
        simics.SIM_process_work(lambda arg: self.cond(), None)
    def send(self, arg=""):
        simics.SIM_trigger_global_message(self.tag + " " + arg, None)

# signal - blocks until one message has been received
class Msg_signal(Global_msg):
    def __init__(self, tag):
        self.init(tag)

# barrier - blocks until all nodes have sent the message
class Msg_barrier(Global_msg):
    def __init__(self, tag, nnodes):
        self.init(tag)
        self.nnodes = nnodes
    def cond(self): return self.count == self.nnodes

# reply - gathers replies from all nodes
class Msg_reply(Msg_barrier):
    def __init__(self, tag, nnodes):
        Msg_barrier.__init__(self, tag, nnodes)
        self.replies = []
    def receive(self, arg):
        self.replies.append(ast.literal_eval(arg))
    def reply(self, arg):
        self.send(repr(arg))

msg_handlers = {}

def global_msg_cb(obj, ref):
    msg = simics.SIM_get_global_message(ref)
    args = msg.split(None, 1)
    tag = args[0]
    if tag in msg_handlers:
        msg_handlers[tag].handle_msg("" if len(args) == 1 else args[1])

simics.SIM_add_global_notifier(simics.Sim_Global_Notify_Message, None,
                               global_msg_cb, global_msg_cb)

class Msg_stop(Global_msg):
    def __init__(self):
        self.init("stop")
    def receive(self, arg):
        simics.SIM_break_simulation(None)

__all__ = ['Global_msg', 'Msg_reply', 'Msg_signal', 'Msg_barrier', 'Msg_stop']
