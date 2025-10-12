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


import table

# Convert a sequence of list and tuples to only lists.
def listify(seq):
    if not isinstance(seq, list) and not isinstance(seq, tuple):
        return seq
    ret = []
    for s in seq:
        ret.append(listify(s))
    return ret

# Update a list of default key/values-pairs (a) with another
# list of key/value-pairs which overrides any default settings.
def merge_keys(a,b):
    d = dict(a)
    d.update(b)
    return listify(list(d.items()))

def merge_keys_without_listify(a,b):
    d = dict(a)
    d.update(b)
    return list(d.items())

class ProbeException(Exception):
    pass

def filter_out_key(kv, key):
    keys = []
    ret = None
    for (k, v) in kv:
        if k == key:
            ret = v
        else:
            keys.append((k,v))
    return (keys, ret)

def filter_out_keys(kv, key_set):
    return [[k, v] for [k, v] in kv if k not in key_set]

def get_key(key, props, default = None):
    for k, v in props:
        if k == key:
            return v
    return default
