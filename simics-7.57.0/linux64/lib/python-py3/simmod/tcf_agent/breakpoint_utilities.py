# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import re
import cli
import json
from . import tcf_common

def split_line(line):
    match = re.match(r'([a-zA-Z]:[^:]+|[^:]*):(\d+)(?::(\d+))?$', line)
    if match is None:
        raise cli.CliError('The line argument must have the format: '
                           '<path>:<line>[:column]')
    else:
        (path, line, col) = match.groups()
        return (path if path else None, int(line), int(col) if col else None)

def create_line_attrs(cmd_type, obj, line_or_filename, line, column,
                      error_not_planted, r, w, x, p, context_query):
    if line_or_filename is None:
        val = None
        arg_name = None
    else:
        (_, val, arg_name) = line_or_filename
    if arg_name == "line":
        if line is not None:
            raise cli.CliError('"line-number" cannot be used together with'
                               ' "line"')
        if column is not None:
            raise cli.CliError('"column" cannot be used together with "line"')
        # The file string can be on the format "<file>:<line>:<column>" and when
        # line is not specified then line and columns are retrieved from that
        # string instead. This will not support files with colons in the
        # filename, for such files line, and possibly column, has to be
        # specified through the line and column arguments.
        (filename, line, column) = split_line(val)
    else:
        if line is None:
            raise cli.CliError('Either "line" or "line-number" must be'
                               ' provided')
        filename = val

    if not filename:
        if not obj:
            obj = tcf_common.get_debug_object()
        success = obj is not None and hasattr(obj.iface, "symdebug")
        if success:
            frame_no = tcf_common.Debug_state.debug_state(obj).frame
            (success, frames) = obj.iface.symdebug.stack_frames(frame_no,
                                                                frame_no)
        provide_str = '"filename" or a file in "line" must be provided'
        if not success or not frames:
            raise cli.CliError(f'No current debug frame, {provide_str}.')
        filename = frames[0].get('file')
        if not filename:
            raise cli.CliError(f'No file for current frame, {provide_str}.')


    # Setup common breakpoint attributes
    access = [0, 0x1][r] | [0, 0x2][w] | [0, 0x4][x or (not (r or w))]
    attrs = {
        'File': filename,
        'Line': line,
        'AccessMode': access,
        'Enabled': True,
        }

    # Setup breakpoint and context specific breakpoint attributes.
    if cmd_type == 'break':
        attrs['ID'] = tcf_common.next_bp_id()
    if p:
        attrs['BreakOnPhysicalAddresses'] = True
    if context_query:
        attrs['ContextQuery'] = tcf_common.simics_query_reformat(context_query)
    if obj:
        attrs['ContextIds'] = [obj.cid]
    if column != None:
        attrs['Column'] = column

    return attrs

def get_line_wait_data(cli_arg):
    '''Return a string describing what is waited on
    (for list-script-branches).'''
    (_, line, _, r, w, x, p) = cli_arg[0:7] # Ignore possible last context_query
    if not x:
        x = (not r) and (not w)
    extra = '('
    if r:
        extra += 'r'
    if w:
        extra += 'w'
    if x:
        extra += 'x'
    if p:
        extra += 'p'
    extra += ')'

    return "'%s' %s" % (line[1], extra)

def create_location_attrs(cmd_type, obj, loc, length, error_not_planted, r,
                          w, x, p, context_query):
    # Setup location and access attributes.
    access = [0, 0x1][r] | [0, 0x2][w] | [0, 0x4][x or (not (r or w))]
    loc_str = loc[1] if (loc[0] == cli.str_t
                         or loc[0] == 'str_t') else hex(loc[1])
    attrs = {
        'Location': loc_str,
        'Size': length,
        'AccessMode': access,
        'Enabled': True,
        'SkipPrologue': True,
        }

    # Setup breakpoint attributes.
    if cmd_type == 'break':
        attrs['ID'] = tcf_common.next_bp_id()
    if p:
        attrs['BreakOnPhysicalAddresses'] = True
    if context_query:
        attrs['ContextQuery'] = tcf_common.simics_query_reformat(context_query)
    if obj:
        attrs['ContextIds'] = [obj.cid]
    return (attrs, loc_str)

def get_location_wait_data(cli_arg):
    '''Return string describing what is waited on (for list-script-branches).'''
    # Ignore possible last context_query
    (_, loc, length, _, r, w, x, p) = cli_arg[0:8]
    if not x:
        x = (not r) and (not w)
    extra = '('
    if r:
        extra += 'r'
    if w:
        extra += 'w'
    if x:
        extra += 'x'
    if p:
        extra += 'p'
    extra += ')'

    if loc[0] == cli.str_t or loc[0] == 'str_t':
        loc_info = "'%s'" % loc[1]
    else:
        loc_info = "0x%x (len:%d)" % (loc[1], length)

    return loc_info + " " + extra

def accesses(bp):
    am = bp.get('AccessMode', 4)
    accesses = [a for (i, a) in enumerate(['read', 'write', 'execution'])
                if am & (1 << i)]
    return ', '.join(accesses)

def get_bp_desc(bp):
    if 'Location' in bp:
        loc = bp['Location']
        return '%s of %s' % (accesses(bp), loc)
    elif 'File' in bp:
        file = bp['File']
        line = bp.get('Line', 0)
        column = bp.get('Column', 0)
        if not all(isinstance(x, int) for x in [line, column]):
            return 'Broken line breakpoint'
        return '%s of %s%s' % (accesses(bp), file,
                               (':%d' % line
                                + (':%d' % column if column else '')
                                if line else ''))
    elif bp.get('EventType', '') in ['context creation',
                                     'context destruction',
                                     'context switch in',
                                     'context switch out']:
        cq = bp.get('ContextQuery', '<nothing>')
        e = bp['EventType'][len('context '):]
        return '%s of contexts matching %s' % (e, cq)
    else:
        return "Unknown TCF breakpoint"

def safe_loads(s):
    try:
        return json.loads(s)
    # json.loads doesn't say what it can raise, but it looks like it
    # TypeErrors and ValueErrors.
    except (ValueError, TypeError):
        return 'Broken json (%s)' % s

def get_instances(status):
    status = json.loads(status)
    return status.get('Instances', [])

def get_hit_counts(agent, instances):
    full_name = agent.iface.agent_proxy_finder.context_full_name
    return dict((full_name(ctx), hits)
                for (ctx, hits) in ((i.get('LocationContext', None),
                                     i.get('HitCount', 0)) for i in instances)
                if ctx and hits)

def get_bp_properties(agent, bp, status):
    """Return a dictionary of breakpoint properties.

    The dictionary will contain all properties of the breakpoint with
    the breakpoint manager mandated names for the known properties and
    a 'desc'."""
    bm_keys = { 'Enabled': 'enabled', 'Temporary': 'temporary',
                'IgnoreCount': 'ignore count' }
    r = dict((bm_keys.get(k, k), safe_loads(v)) for (k, v) in bp.items())
    r.setdefault('enabled', False)
    r.setdefault('temporary', False)
    r.setdefault('ignore count', 0)
    r['description'] = get_bp_desc(r)
    instances = get_instances(status)
    r['hit count'] = get_hit_counts(agent, instances)
    r['planted'] = any([not 'Error' in i for i in instances])
    return r
