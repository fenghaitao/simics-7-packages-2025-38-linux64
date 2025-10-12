# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics, cli, conf

# Simics object doing post_instantiate tasks. Could be replaced
# with a function registering tasks to be done after instantiation.

class ScriptEngine:
    wait_obj: simics.conf_object_t|None
    input_obj: simics.conf_object_t|None
    script: list[str]
    index: int

    cls = simics.confclass(
        'script-engine',
        short_doc = "scripted interaction with a console")
    cls.doc = "Class for scripted interaction with a console object."

    cls.attr.script("[s*]", default = [],
                    doc = "Script, as a list of strings.")
    # fisketur[useless-method-call]
    cls.attr.index("i", default = 0,
                   doc = "Current script line.")
    cls.attr.input_obj("o|n", default = None,
                       doc = "Object with an 'input' command.")
    cls.attr.wait_obj(
        "o|n", default = None,
        doc = "Object with a 'bp-wait-for-console-string' command.")

    @cls.objects_finalized
    def objects_finalized(self):
        (wo, io) = (self.wait_obj, self.input_obj)
        self.clock = simics.SIM_object_clock(self.obj)
        if wo and io:
            simics.SIM_run_alone(self._start_sb, None)

    def _start_sb(self, _):
        self._sb = cli.sb_create(self._sb_engine)

    def _wait(self, s):
        conf.bp.console_string.cli_cmds.wait_for(
            object = self.wait_obj, string = s)
    def _type(self, s):
        self.input_obj.cli_cmds.input(string = s)
    def _sleep(self, s):
        self.clock.cli_cmds.wait_for_time(seconds = float(s), _relative = True)

    def _sb_engine(self):
        table = {
            'w': self._wait,
            'i': self._type,
            's': self._sleep,
        }
        while True:
            try:
                for x in self.script[self.index:]:
                    (cmd, _, s) = x.partition(":")
                    if cmd in table:
                        table[cmd](s)
                        self.index += 1
            except cli.CliQuietError:
                continue
            break
