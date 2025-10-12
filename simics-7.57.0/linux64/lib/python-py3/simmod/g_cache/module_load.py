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


from .gcache_common import *

def gc_info_cmd(gc):
    default_returns = gc_default_info_cmd(gc)
    return default_returns + [(None,
             [('Read penalty of cycles', gc.penalty_read),
              ('Write penalty of cycles', gc.penalty_write),
              ('Read-next penalty of cycles', gc.penalty_read_next),
              ('Write-next penalty of cycles', gc.penalty_write_next),
              ('Snoopers', gc.snoopers if gc.snoopers else "None"),
              ('Higher level caches', gc.higher_level_caches if gc.higher_level_caches \
                                                             else "None")])]

def gc_stats_cmd(gc):
    gc_default_stats_cmd(gc, 1)

gc_define_cache_commands("g-cache", None, gc_info_cmd, gc_stats_cmd, None)
