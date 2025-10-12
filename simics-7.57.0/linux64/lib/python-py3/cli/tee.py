# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os
import codecs
import datetime
import simics
from .errors import CliError

class TeeInfo:
    def __init__(self, filename, file_obj, timestamp):
        self.filename = filename
        self.file_obj = file_obj
        self.timestamp = timestamp
        self.ends_with_newline = True

    def init(self):
        simics.SIM_add_output_handler(tee_handler, self)

    def write(self, buf):
        if self.timestamp:
            now = datetime.datetime.now()
            timestamp = now.strftime("[%H:%M:%S.%f")[:-3] + '] '
            if self.ends_with_newline:
                self.file_obj.write(timestamp)
            buf = buf[:-1].replace("\n", "\n" + timestamp) + buf[-1]
            self.ends_with_newline = buf.endswith("\n")
        self.file_obj.write(buf)
        self.file_obj.flush()

    def close(self):
        simics.SIM_remove_output_handler(tee_handler, self)
        self.file_obj.close()

# list of active TeeInfos
all_tee_objs = []

def tee_handler(tee_info, buf, count):
    tee_info.write(buf)

def tee_add(filename, overwrite, append, timestamp):
    if not overwrite and not append and os.path.exists(filename):
        raise CliError("File %s already exists." % filename)
    try:
        file_obj = codecs.open(filename, "a" if append else "w", "utf-8")
    except:
        raise CliError("Failed to open '%s' for writing" % filename)
    tee_info = TeeInfo(filename, file_obj, timestamp)
    tee_info.init()
    all_tee_objs.append(tee_info)

def tee_remove(filename):
    if not all_tee_objs:
        print("No output file active.")
        return
    for tee_info in all_tee_objs[:]:
        if filename is None or filename == tee_info.filename:
            tee_info.close()
            all_tee_objs.remove(tee_info)
            if filename:
                return
    if filename:
        raise CliError("Output not redirected to file '%s'" % filename)

def tee_expander(string):
    from .impl import get_completions
    return get_completions(string, [x.filename for x in all_tee_objs])
