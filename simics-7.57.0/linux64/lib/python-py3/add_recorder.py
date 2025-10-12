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


from configuration import *
import update_checkpoint

def add_recorder(cls, config):
    changed = []
    added = []
    consoles = update_checkpoint.all_objects(config, cls)
    for console in consoles:
        if hasattr(console, "recorder"):
            continue

        recorders = update_checkpoint.all_objects(config, "recorder")
        if not recorders:
            rec_name = get_available_object_name(config, "rec")
            rec = pre_conf_object(rec_name, "recorder")
            config[rec_name] = console.queue
            added.append(rec)
        else:
            rec = recorders[0]

            # prefer a recorder in the same cell as the console
            if (hasattr(console, "queue") and console.queue and
                hasattr(console.queue, "cell") and console.queue.cell):
                for r in recorders:
                    if hasattr(r, "queue") and r.queue and hasattr(r.queue, "cell"):
                        if r.queue.cell == console.queue.cell:
                            rec = r
                            break

        console.recorder = rec
        changed.append(console)

    return ([], changed, added)
