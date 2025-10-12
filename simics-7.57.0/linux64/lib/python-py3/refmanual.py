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


import cli_impl
import collections
import inspect
import os
import pydoc
import re
import sys
import traceback
import operator
import itertools
import unittest
import io
from pathlib import Path

from cli import (
    CliError,
    arg,
    expand_path_markers,
    file_expander,
    flag_t,
    format_print,
    get_format_string,
    get_object,
    get_synopses,
    get_synopsis,
    hap_c_arguments,
    new_command,
    print_columns,
    print_wrap_code,
    simics_commands,
    str_t,
    terminal_width,
    visible_objects,
    )

from simics import (
    SIM_get_all_classes,
    SIM_get_all_modules,
    SIM_get_class,
    Sim_Attr_Class,
    Sim_Attr_Flag_Mask,
    Sim_Attr_Integer_Indexed,
    Sim_Attr_Internal,
    Sim_Attr_List_Indexed,
    Sim_Attr_Persistent,
    Sim_Attr_Required,
    Sim_Attr_String_Indexed,
    VT_get_port_classes,
)

from alias_util import (
    obj_aliases,
    user_defined_aliases
)

import conf
from cli_impl import cli_command
import simics
from functools import total_ordering
from simicsutils.internal import latest_api_version, default_api_version
from io import StringIO
import builtins

from functools import reduce

#
# Some constants to play with
#

# minimum number of elements for a "long" table
min_long_table = 10

# core 'module' definitions
core_module = "Simics Core"
core_module_file = "libsimics-common.so"

#
# Functions to handle labels and ids
#

# remove characters that are not allowed in ids
def labelEncode(str):
    res_str = ''
    for c in str:
        if c == '<':
            res_str = res_str + '_lt_'
        elif c == '>':
            res_str = res_str + '_gt_'
        elif c == '&':
            res_str = res_str + '_amp_'
        elif c == '|':
            res_str = res_str + '_binor_'
        else:
            res_str = res_str + c
    return res_str

# return a base id for a class
def classId(c):
    return '__rm_class_' + labelEncode(c)

# return a base id for a component
def componentId(c):
    return '__rm_component_' + labelEncode(c)

# return a base id for a module
def moduleId(m):
    return '__rm_module_' + labelEncode(m)

# return a base id for a command
def commandId(c):
    return '__rm_command_' + labelEncode(c)

# return a base id for an interface
def ifcId(c):
    return '__rm_interface_' + labelEncode(c)

# return a base id for an attribute
def attrId(c, a):
    return '__rm_attribute_' + labelEncode(c) + '_' + labelEncode(a)

# return a base id for a hap
def hapId(h):
    return '__rm_hap_' + labelEncode(h)

# return a base id for a notifier
def notifierId(h):
    return '__rm_notifer_' + labelEncode(h)

#
# Misc. helper functions
#

def concat_comma(l, word = "or"):
    '''Returns the sequence 'l' concatenated with commas and 'word'
    for the last item (uses Oxford commas).'''
    if not l:
        return ''
    if len(l) == 1:
        return l[0]
    if len(l) == 2:
        return '%s %s %s' % (l[0], word, l[1])
    l = list(l)
    l[-1] = '%s %s' % (word, l[-1])
    return ', '.join(l)

class _test_concat_comma(unittest.TestCase):
    def test_concat_comma(self):
        self.assertEqual(concat_comma([]), '')
        self.assertEqual(concat_comma(['x']), 'x')
        self.assertEqual(concat_comma(['x', 'y']), 'x or y')
        self.assertEqual(concat_comma(['x', 'y', 'z']), 'x, y, or z')
        self.assertEqual(concat_comma(['x', 'y', 'z'], word = 'and'),
                         'x, y, and z')

def type_options(t):
    level = 0
    current = ''
    for c in t:
        if c == '|' and level == 0:
            yield current
            current = ''
        else:
            current += c
            if c == '[':
                level += 1
            elif c == ']':
                level -= 1
    yield current

class _test_type_options(unittest.TestCase):
    def test_type_options(self):
        self.assertEqual(list(type_options('o')), ['o'])
        self.assertEqual(list(type_options('o|n')), ['o', 'n'])
        self.assertEqual(list(type_options('[o|i]')), ['[o|i]'])
        self.assertEqual(list(type_options('[o|i]|o')), ['[o|i]', 'o'])

# return a human-readable string based on the attribute type t, a
# string of "|"-separated type specification characters
def type_encode(t):
    types = {
        "a": "any",
        "d": "data",
        "f": "float",
        "i": "integer",
        "n": "nil",
        "o": "object",
        "s": "string",
        "b": "boolean",
        "D": "dictionary"
        }
    def nil_last(k):
        return 'b' + k if k == 'nil' else 'a' + k
    t = sorted([types.get(t, t) for t in type_options(t)],
               key=nil_last)
    return concat_comma([ '<tt>%s</tt>' % tt for tt in t])

class _test_type_encode(unittest.TestCase):
    def test_type_encode(self):
        self.assertEqual(type_encode('i'), '<tt>integer</tt>')
        self.assertEqual(type_encode('d|D'), '<tt>data</tt> or <tt>dictionary</tt>')
        self.assertEqual(type_encode('n|s'), '<tt>string</tt> or <tt>nil</tt>')
        self.assertEqual(type_encode('s|n'), '<tt>string</tt> or <tt>nil</tt>')
        self.assertEqual(type_encode('Z'), '<tt>Z</tt>')
        self.assertEqual(type_encode('[os]'), '<tt>[os]</tt>')
        self.assertEqual(type_encode('i|[os]'), '<tt>[os]</tt> or <tt>integer</tt>')
        self.assertEqual(type_encode('i|[o|s]'), '<tt>[o|s]</tt> or <tt>integer</tt>')


# compare two commands by name
def sort_key_cmd(a):
    return a.name.lower()

# compare two description items (module, class, attr, ..) by name
def sort_key_item(a):
    return a.name.lower()

# Strip away the namespace from a command name
def stripCommandName(c):
    return c[c.rfind('.')+1:]


import codecs

#
# Output handlers
#
class GenericOutputHandler:
    def __init__(self, output_file):
        self.of = codecs.open(output_file, "w", "utf-8")

    # Returns true if the backend will handle <insert> tags correctly.
    # This also implies that text in an <add> doesn't immediately show
    # up on the output medium.
    def supports_insert(self):
        raise NotImplementedError

    # output functions
    def pr(self, s):
        self.of.write(s)
    def pn(self, s):
        self.of.write(s + "\n")

    #
    # output dependent functions
    #

    # encode special character for output
    # encode for XML output
    def encode(self, str):
        res_str = ''
        for c in str:
            if c == '<':
                res_str = res_str + '&lt;'
            elif c == '>':
                res_str = res_str + '&gt;'
            elif c == '&':
                res_str = res_str + '&amp;'
            else:
                res_str = res_str + c
        return res_str

    # return a link towards 'label' with text 'text'
    def makeLink(self, label, text):
        return text

    # return an index entry made from 'list'
    def makeIndex(self, list):
        return ""

    # equivalent to <add id="..." label="..."><name>...</name> ... </add>
    def beginAdd(self, id, label, name, type = ''):
        pass
    def endAdd(self):
        pass

    # equivalent to <section .../>
    def printSection(self, numbering, id):
        pass

    # equivalent to <doc> ... </doc>
    def beginDoc(self):
        pass
    def endDoc(self):
        pass

    # equivalent to <di type=""> + eventual <di-name>
    def beginDocItem(self, name):
        pass
    # equivalent to </di>
    def endDocItem(self):
        pass

    # tables
    def beginTable(self, length, border = "false"):
        pass
    def endTable(self):
        pass
    def beginRow(self):
        pass
    def endRow(self):
        pass
    def beginCell(self):
        pass
    def endCell(self):
        pass

    def makeTable(self, str):
        return str
    def makeCell(self, str, size=0):
        return str

    # description list
    def beginDList(self):
        pass
    def endDList(self):
        pass
    def beginDListTitle(self):
        pass
    def endDListTitle(self):
        pass
    def makeDListTitle(self, text):
        return text
    def beginDListItem(self):
        pass
    def endDListItem(self):
        pass

    # quote a string
    def q(self, text):
        return '"' + text + '"'

    #
    # list: list of strings to print
    # link_transform: how to create the link name for nref
    # text_transform: change text before printing
    # pre: what to print before each element
    # post: what to print after each element
    # sep: what to print between each element
    #
    def printListWithSep(self, list, link_transform, text_transform,
                         pre, post, sep):
        l = len(list)
        for i in range(0, l):
            self.pr(pre)
            if link_transform:
                tr = link_transform(list[i])
            else:
                tr = None

            text = text_transform(list[i])
            if tr:
                text = self.makeLink(tr, text)

            if i != l - 1:
                tail = post + sep
            else:
                tail = post

            # print 'tail' together with 'text' to prevent line break
            # (only works well for the terminal backend if there are
            # no tags between the text and punctuation)
            self.pr(text + tail)

    def flush(self):
        pass

def strlen_without_tags(str):
    return reduce(lambda n, s: n + len(s), re.split(r'<[^>]*>', str), 0)

#
# JDocu specialized output handler
#
class JdocuOutputHandler(GenericOutputHandler):

    def __init__(self, filename):
        GenericOutputHandler.__init__(self, filename)
        self.in_dlist_item = False

    def supports_insert(self):
        return True

    # return a link towards 'label' with text 'text'
    def makeLink(self, label, text):
        return '<nref label="' + label + '">' + text + '</nref>'

    # return an index entry made from 'list'
    def makeIndex(self, list):
        return '<ndx>' + "!".join(list) + '</ndx>'

    # return a target link with 'label'
    def makeTarget(self, label):
        return '<ntarget label="' + label + '"/>'

    def beginAdd(self, id, label, name, type = ''):
        self.pr('<add id="' + id + '"')
        if label:
            self.pr(' label="' + label + '"')
        self.pn('>')
        if name:
            self.pn('<name>' + name + '</name>')
    def endAdd(self):
        self.pn('</add>')

    def printSection(self, numbering, id):
        self.pn('<section numbering="' + numbering + '" id="' + id + '"/>')

    # equivalent to <doc>
    def beginDoc(self):
        self.pn('<doc>')
    # equivalent to </doc>
    def endDoc(self):
        self.pn('</doc>')

    # equivalent to <di type=""> + eventual <di-name>
    def beginDocItem(self, name):
        lname = name.lower()
        type = ""
        if lname in ("name", "short", "synopsis", "description", "parameters",
                     "returnvalue", "exceptions", "exec-context"):
            type = lname
        if type:
            self.pn('<di type="' + type + '">')
        else:
            self.pn('<di>\n<di-name>' + name + '</di-name>')

    # equivalent to </di>
    def endDocItem(self):
        self.pn('</di>')

    # tables
    def beginTable(self, length, border = "false"):
        if length > min_long_table:
            self.pn('<table long="true" border="%s">' % border)
        else:
            self.pn('<table long="false" border="%s">' % border)
    def endTable(self):
        self.pn('</table>')
    def beginRow(self):
        self.pr('<tr>')
    def endRow(self):
        self.pn('</tr>')
    def beginCell(self):
        self.pr('<td>')
    def endCell(self):
        self.pr('</td>')

    def makeTable(self, str):
        return '<table>' + str + '</table>'
    def makeCell(self, str, size=0):
        return '<td>' + str + '</td>'

    # description list
    def beginDList(self):
        assert not self.in_dlist_item
        self.pn('<dl>')
    def endDList(self):
        if self.in_dlist_item:
            self.pr('</dd>')
            self.in_dlist_item = False
        self.pn('</dl>')
    def beginDListTitle(self):
        assert not self.in_dlist_item
        self.pr('<dt>')
    def endDListTitle(self):
        assert not self.in_dlist_item
        self.pn('</dt>')
    def makeDListTitle(self, text):
        return '<dt>' + text + '</dt>'
    def beginDListItem(self):
        if not self.in_dlist_item:
            self.pr('<dd>')
            self.in_dlist_item = True
        else:
            self.pr('\n\n')
    def endDListItem(self):
        assert self.in_dlist_item
        self.pr('</dd>')
        self.in_dlist_item = False



#
# JDocu specialized output handler
#
class TerminalOutputHandler(GenericOutputHandler):
    def __init__(self):
        self.buffer = StringIO()

    def supports_insert(self):
        return False

    # output functions
    def pr(self, s):
        self.buffer.write(s)

    def pn(self, s):
        self.pr(s)
        self.pr('\n\n')

    # return a link towards 'label' with text 'text'
    def makeLink(self, label, text):
        return text

    # return an index entry made from 'list'
    def makeIndex(self, list):
        return ''

    # return a target link with 'label'
    def makeTarget(self, label):
        return ''

    def beginAdd(self, id, label, name, type = ''):
        if type:
            self.pr('<dt><i>%s <b>%s</b></i></dt><br/>\n<dd>\n' % (
                    type, name))
        elif name:
            self.pr('<dt><b>' + name + '</b></dt><br/>\n<dd>\n')
    def endAdd(self):
        self.pr('</dd>')

    def printSection(self, numbering, id):
        pass

    # equivalent to <doc>
    def beginDoc(self):
        self.beginDList()
    # equivalent to </doc>
    def endDoc(self):
        self.endDList()

    # equivalent to <di type=""> + eventual <di-name>
    def beginDocItem(self, name):
        lname = name.lower()
        type = ""
        if (lname == "name" or
            lname == "short" or
            lname == "synopsis" or
            lname == "description" or
            lname == "parameters" or
            lname == "returnvalue" or
            lname == "exceptions"):
            type = lname
        if type:
            self.pr('<dt><b>' + name.capitalize() + '</b></dt>\n')
        else:
            self.pr('<dt><b>' + name + '</b></dt>\n')
        self.pr('<dd>\n')

    # equivalent to </di>
    def endDocItem(self):
        self.pr('</dd>')

    # tables
    def beginTable(self, length, border = "False"):
        pass
    def endTable(self):
        pass
    def beginRow(self):
        pass
    def endRow(self):
        self.pr('<br/>\n')
    def beginCell(self):
        pass
    def endCell(self):
        self.pr(' ')

    def makeTable(self, str):
        return str
    def makeCell(self, str, size = 20):
        l = strlen_without_tags(str)
        return str + '&nbsp;' * (1 if l > (size-1) else size - l)

    # description list
    def beginDList(self):
        self.pr('<dl>\n')
    def endDList(self):
        self.pr('</dl>\n')
    def beginDListTitle(self):
        self.pr('<dt><b>')
    def endDListTitle(self):
        self.pr('</b></dt>\n')
    def makeDListTitle(self, text):
        return '<dt>%s</dt>' % (text,)
    def beginDListItem(self):
        self.pr('<dd>\n')
    def endDListItem(self):
        self.pr('</dd>\n')

    def flush(self):
        format_print(self.buffer.getvalue())
        self.buffer = StringIO()

def find_containing_package(module_so):
    # pkg/linux64/lib/module.so -> pkg
    pkg = Path(module_so).parent.parent.parent.resolve()

    # Pick the matching package with the lowest number.
    # This makes it work correctly for Internal (number 0).

    matches = {number: name
        for [_, name, number, _, _, _, _, _, _, path, _, _, _, _]
        in conf.sim.package_info if pkg.samefile(path)}
    if matches:
        return matches[min(matches)]
    else:
        return None

def module_package(module):
    '''Returns the short-name of a module's package or None'''

    if module == core_module:
        return None

    mdata = [ md for md in SIM_get_all_modules() if md[0] == module ]
    if len(mdata) != 1:
        return None

    [(_, mfile, *_)] = mdata
    return find_containing_package(mfile)

def module_package_suffix(module):
    '''Returns a string to be printed after the module name 'module'
    that describes which installation package the module comes from.'''
    package_short = module_package(module)
    return ' (from %s)' % (package_short,) if package_short else ''

def get_module_encode(o, online):
    def _module_encode(module):
        if online:
            module += module_package_suffix(module)
        return o.encode(module)
    return _module_encode

#
# Generic Description Container
#
class GenericDesc:
    def __init__(self, verbose = 1):
        self.verbose = verbose
    def verbosePrint(self, str):
        if self.verbose:
            print(str)

#
# Command Description
#
class CmdDesc(GenericDesc):
    def __init__(self, verbose, name, cmd):
        self.name = name
        self.cmd = cmd
        self.module = None              # if this is a module command
        self.verbose = verbose
        self.doc_with_list = []

    def __repr__(self):
        return (f"CmdDesc(name={self.name}, cmd={self.cmd},"
                f" module={self.module})")

    def getSynopsis(self, command_list):
        if self.doc_with_list:
            syn_cmd_list = []
            for c in self.doc_with_list:
                if c in command_list:
                    syn_cmd_list.append(c)
        elif self.cmd.doc_with and self.cmd.doc_with in command_list:
            main_cmd = command_list[self.cmd.doc_with]
            syn_cmd_list = []
            for c in main_cmd.doc_with_list:
                if (c != self.name) and c in command_list:
                    syn_cmd_list.append(c)
            syn_cmd_list.append(main_cmd.name)
        else:
            syn_cmd_list = []

        synopses = get_synopses(self.cmd, 'jdocu')
        for cmd in sorted(syn_cmd_list):
            synopses += get_synopses(command_list[cmd].cmd, 'jdocu')

        return '<br/>'.join(synopses)

    def getDoc(self, command_list, avoided_command_list):
        if self.cmd.doc_with:
            if self.cmd.doc_with in command_list:
                doc = command_list[self.cmd.doc_with].cmd.doc
            elif self.cmd.doc_with in avoided_command_list:
                doc = avoided_command_list[self.cmd.doc_with].cmd.doc
            else:
                raise DocException(f'doc_with for command {self.cmd} failed')
        else:
            doc = self.cmd.doc
        return doc

    def getSeeAlso(self, command_list, avoided_command_list):
        if self.cmd.doc_with:
            if self.cmd.doc_with in command_list:
                s = command_list[self.cmd.doc_with].cmd.see_also
            elif self.cmd.doc_with in avoided_command_list:
                s = avoided_command_list[self.cmd.doc_with].cmd.see_also
            else:
                assert(False)  # Should never get here, expect raise in getDoc
        else:
            s = self.cmd.see_also
        return s

    def printLong(self, o, doc, id = '', online = 0,
                  namespace = None, no_extern_link = 0):
        command_list = doc.commands
        avoided_command_list = doc.avoided_commands
        if online:
            cmd_name = o.encode(self.cmd.name)
        else:
            cmd_name = o.encode(stripCommandName(self.cmd.name))
        o.beginAdd(id, "", cmd_name, 'Command')
        o.pr(o.makeTarget(commandId(self.cmd.name)))

        if namespace:
            o.pr(o.makeIndex([o.encode(stripCommandName(self.name)),
                              "namespace command",
                              namespace]))
        else:
            o.pr(o.makeIndex([o.encode(self.name)]))

        o.beginDoc()

        # name
        if not online:
            o.beginDocItem('name')
            o.pr('<b>' + o.encode(self.cmd.name))
            if self.cmd.is_deprecated():
                o.pr(' &mdash; <i>deprecated</i>')
            o.pr('</b>')
            o.endDocItem()
        else:
            prefix = "<b>Warning:</b> %s is " % o.encode(self.cmd.name)
            if self.cmd.is_deprecated():
                o.pr(prefix + "deprecated\n\n")
            elif self.cmd.preview:
                o.pr(prefix + "internal and unsupported\n\n")

        # aliases
        if (self.cmd.alias):
            o.beginDocItem('Alias')
            aliases = self.cmd.alias_names()
            for a in aliases:
                if namespace:
                    o.pr(o.makeIndex([o.encode(stripCommandName(a)),
                                      "namespace command",
                                      namespace]))
                else:
                    o.pr(o.makeIndex([o.encode(a)]))

            o.printListWithSep(aliases, None, o.encode, "", "", ", ")
            o.endDocItem()

        # synopsis
        o.beginDocItem('synopsis')
        o.pr(self.getSynopsis(command_list))
        o.endDocItem()

        # description
        o.beginDocItem('description')
        doc_str = self.getDoc(command_list, avoided_command_list).strip()
        def format_command_ref(e):
            cmd = doc.commands.get(e)
            if cmd and cmd.module in doc.modules and not no_extern_link:
                return o.makeLink(commandId(e), o.encode(e))
            return o.encode(e)
        if self.cmd.is_deprecated():
            alt_cmds = self.cmd.deprecated
            o.pr(self.get_replacement_msg(
                "deprecated", format_command_ref, alt_cmds))
            if doc_str:
                o.pn('')
                o.pn('')
        if self.cmd.is_legacy():
            alt_cmds = self.cmd.legacy
            o.pr(self.get_replacement_msg(
                "legacy", format_command_ref, alt_cmds))
            if doc_str:
                o.pn('')
                o.pn('')
        o.pr(doc_str.rstrip())
        o.endDocItem()

        # provided by
        if self.module:
            o.beginDocItem('Provided By')
            o.pr(self.module if no_extern_link
                 else o.makeLink(moduleId(self.module), self.module))
            if online:
                o.pr(module_package_suffix(self.module))
            o.endDocItem()

        # doc items
        if self.cmd.doc_items:
            for di in self.cmd.doc_items:
                o.beginDocItem(di[0].capitalize())
                # hack around See Also
                if di[0].lower() == "see also":
                    o.pr(o.encode(di[1].strip()))
                else:
                    o.pr(di[1].strip())
                o.endDocItem()

        # see also
        see_also = self.getSeeAlso(command_list, avoided_command_list)
        # Add alternate commands specified in the deprecated argument to see
        # also. May be a string or some kind of sequence of strings...
        if self.cmd.is_deprecated():
            alt_cmds = self.cmd.deprecated
            if isinstance(self.cmd.deprecated, str):
                alt_cmds = (alt_cmds,)
            if isinstance(alt_cmds, collections.abc.Sequence):
                for alt_cmd in alt_cmds:
                    if (isinstance(alt_cmd, str)
                        and alt_cmd in command_list
                        and alt_cmd not in see_also):
                        see_also = see_also + [alt_cmd]
        if see_also:
            for c in see_also:
                if not online and not c in command_list:
                    self.verbosePrint(
                        "CmdDesc::printLong(): " +
                        "*** unknown see also reference in command "
                        + self.cmd.name +": " + c)
            o.beginDocItem('See Also')
            o.pr(", ".join(format_command_ref(cmd) for cmd in see_also))
            o.endDocItem()

        o.endDoc()
        o.endAdd()

    @staticmethod
    def get_replacement_msg(what, format_command_ref, alt_cmds):
        if alt_cmds is True:
            msg = f'This command is {what}; no replacement available.'
        else:
            if isinstance(alt_cmds, str):
                alt_cmds = [alt_cmds]
            def or_join(lst):
                if len(lst) > 1:
                    return ", ".join(lst[:-1]) + " or " + lst[-1]
                return ", ".join(lst)
            replacements = or_join([format_command_ref(e) for e in alt_cmds])
            msg = f'This command is {what}; use {replacements} instead.'
        return msg

    def printComponentCommand(self, o, doc, id = '',
                              namespace = None, no_extern_link = 0):
        cmd_name = o.encode(stripCommandName(self.cmd.name))
        o.beginAdd(id, "", cmd_name, 'Command')
        o.pr(o.makeTarget(commandId(self.cmd.name)))

        if namespace:
            o.pr(o.makeIndex([o.encode(stripCommandName(self.name)),
                              "namespace command",
                              namespace]))
        else:
            o.pr(o.makeIndex([o.encode(self.name)]))
        o.pn(get_synopsis(self.cmd, 0, "jdocu") + '<br/>')
        o.endAdd()

#
# Module Description
#
class ModuleDesc(GenericDesc):
    def __init__(self, verbose, name, filename, classes, port_classes):
        self.verbose = verbose
        self.name = name
        self.filename = filename
        self.classes = classes
        self.port_classes = port_classes
        self.commands = {}
        self.haps = simics.CORE_get_implemented_haps(name)

    def print_name(self, o):
        o.pr(self.name)

    def print_short(self, o):
        o.pr(self.name)

    def printLong(
            self, o, doc, online = 0, no_extern_link = 0, include_haps = True):
        id = moduleId(self.name)
        o.beginDoc()

        # name
        if not online:
            o.pr(o.makeTarget(id))
            o.beginDocItem('name')
            o.pr(o.encode(self.name))
            o.endDocItem()
        else:
            o.beginAdd('', '', self.name, 'Module')

        o.pr(o.makeIndex([self.name]))

        pkg = module_package(self.name)
        if online and pkg:
            o.beginDocItem('Package')
            o.pr(pkg)
            o.endDocItem()

        # classes
        if self.classes:
            o.beginDocItem('Classes')
            o.beginTable(len(self.classes))
            for c in sorted(self.classes):
                cl = doc.classes[c]
                o.beginRow()
                o.pr(o.makeCell(cl.name if no_extern_link
                                else o.makeLink(classId(cl.name), cl.name)))
                o.endRow()
            o.endTable()
            o.endDocItem()

        # haps
        if self.haps and include_haps:
            o.beginDocItem('Haps')
            o.beginTable(len(self.haps))
            self.haps.sort()
            def hap_id(h):
                if no_extern_link:
                    return h
                else:
                    return o.makeLink(hapId(h), h)
            for h in self.haps:
                o.beginRow()
                o.pr(o.makeCell(hap_id(h)))
                o.endRow()
            o.endTable()
            o.endDocItem()
        if self.commands:
            o.beginDocItem('Global Commands')
            o.beginTable(len(self.commands))
            cmds = list(self.commands.values())
            for c in sorted(cmds, key=sort_key_item):
                o.beginRow()
                o.pr(o.makeCell(o.encode(c.cmd.name)
                                if (no_extern_link
                                    or c.cmd.name not in doc.commands
                                    or (doc.commands[c.cmd.name].module
                                        not in doc.modules))
                                else o.makeLink(commandId(c.cmd.name),
                                                o.encode(c.cmd.name))))
                o.beginCell()
                if c.cmd.is_deprecated():
                    o.pr("<i>deprecated</i> &mdash; ")
                o.pr(c.cmd.short)
                o.endCell()
                o.endRow()
            o.endTable()
            o.endDocItem()
        o.endDoc()

#
# group connectors with same base-name together
#
def group_connector_info(connectors):
    def add_cnt_info(base, start, end, info):
        if end != start:
            new_cnts['%s[%s-%s]' % (base, start, end)] = info
        else:
            new_cnts['%s%s' % (base, start)] = info

    new_cnts = {}
    cnt_info = {}
    for cnt in connectors:
        m = re.match('(.*?)([0-9]*)$', cnt)
        if not m.group(2):
            new_cnts[m.group(1)] = connectors[cnt]
        else:
            cnt_info.setdefault(m.group(1), []).append(m.group(2))
    for (base, suffixes) in cnt_info.items():
        if any((s.startswith('0') and s != '0') for s in suffixes):
            # If we have 0 prefixed numbers we have non-standard
            # numbering. Don't try to be smart; just list every
            # connector as its own entry.
            for s in suffixes:
                c = base + s
                new_cnts[c] = connectors[c]
        else:
            # Group the connectors. We take the sorted list of
            # suffixes and group them based on the suffix and
            # connector info.
            suffixes.sort(key=int)
            # we always have at least one suffix for the base
            prev = start = suffixes[0]
            info = connectors[base + start]
            for suffix in suffixes[1:]:
                # If there is a hole in the range or if the connector
                # info changes, start a new group.
                if (int(prev) + 1 != int(suffix)
                    or info != connectors[base + suffix]):
                    add_cnt_info(base, start, prev, info)
                    prev = start = suffix
                    info = connectors[base + start]
                else:
                    prev = suffix
            add_cnt_info(base, start, prev, info)
    return new_cnts

def extract_indices(portname):
    '''Split a string containing []-enclosed integers into a pair
    (fmt, indices), such that fmt % indices == portname'''
    indices = []
    fmt = ''
    for s in portname.split(']'):
        if '[' in s:
            (name, idx) = s.split('[')
            indices.append(int(idx))
            fmt += name + '[{}]'
        else:
            fmt += s
    return (fmt, indices)

class _test_extract_indices(unittest.TestCase):
    def runTest(self):
        for (input, result) in [
                ('x', ('x', [])),
                ('x[3]', ('x[{}]', [3])),
                ('foo[18][3].bar[8].x', ('foo[{}][{}].bar[{}].x', [18, 3, 8]))]:
            self.assertEqual(extract_indices(input), result)

def is_cartesian_product(coords):
    '''If coords are the cartesian product of some zero-based integer ranges,
    return a tuple of these range sizes. Otherwise return False.'''
    # handle duplicates, for completeness
    coords = set(map(tuple, coords))
    # all coordinates have the same number of dimensions
    assert len(set(map(len, coords))) == 1
    # axes[n] is the set of values in index n of a coordinate
    axes = [set(axis) for axis in zip(*coords)]
    assert all(isinstance(x, int) for axis in axes for x in axis)
    # If the values along one axis ranges from 0 to n-1, then n is the
    # only possible range size. A cartesian product contains all
    # possible combinations of values in the range, so since the
    # coordinates in the input set are unique, it's sufficient to
    # check if the number of elements matches.
    if not all(min(axis) == 0 for axis in axes):
        return False
    sizes = [max(axis) + 1 for axis in axes]
    if len(coords) != reduce(operator.mul, sizes, 1):
        return False
    return sizes

class _test_is_cartesian_product(unittest.TestCase):
    def runTest(self):
        for bad in [
                # not zero-based
                [(1,)],
                # incomplete
                [(0,), (2,)],
                [(0, 0), (0, 1), (1, 1)]]:
            self.assertEqual(is_cartesian_product(bad), False)
        for (coords, sizes) in [
                ([()], []),
                ([(0,)], [1]),
                ([(0,), (1,)], [2]),
                ([(0, 0)], [1, 1]),
                ([(0, 1), (0, 0), (1, 1), (1, 0)], [2, 2]),
                (itertools.product(range(2), range(5), range(3)),
                 [2, 5, 3])]:
            self.assertEqual(is_cartesian_product(coords), sizes)

def nonredundant_iface_ports(cls):
    '''Return the set of interface ports of a class which do not have a
    corresponding port object. This is returned as a dictionary
    {name: (dims, ifaces, desc)} where dims is () for a single port and (size,)
    for a port array; ifaces is a list of interface names;
    and desc is a docstring'''
    obj_ports = set(VT_get_port_classes(cls))
    port_ifaces = {}
    for (p, num, i) in simics.VT_get_port_interfaces(cls):
        portname = p + ('[%d]' % (num - 1,) if num > 1 else '')
        if 'port.' + portname in obj_ports or 'bank.' + portname in obj_ports:
            # an (object) port with the same name as this (interface)
            # port exists; assume that the interface port is redundant
            continue
        name = p + ('[%d]' % (num,) if num > 1 else '')
        if p not in port_ifaces:
            port_ifaces[name] = (
                (num,) if num > 1 else (),
                [],
                simics.CORE_get_port_description(cls, p))
        (n, ifaces, desc) = port_ifaces[name]
        ifaces.append(i)
    return port_ifaces

#
# Class Description
#
class ClassDesc(GenericDesc):
    def __init__(self, verbose, online, c, module):
        self.verbose = verbose
        self.online = online
        info = simics.VT_get_class_info(c)

        self.name = c
        self.description = info[0]
        if not self.description:
            self.verbosePrint("ClassDesc() *** no description for class " + c)
            self.description = ("<todo>No description for class %s</todo>"
                                % (c,))
        self.kind = info[1]
        self.ifc_list = info[2]
        # we ignore info[3], the list of attributes, as it will be
        # created by scan_attr_info() if requested
        self.module = module

        self.port_ifaces = nonredundant_iface_ports(c)

        self.commands = {}
        self.scanned_attr_info = False

    # this is an ugly hack to lazily read all the attribute
    # information
    def __getattr__(self, attr):
        if self.scanned_attr_info:
            raise AttributeError('%s instance has no attribute %r' % (
                    self.__class__.__name__, attr))
        self.scan_attr_info()
        return getattr(self, attr)

    def scan_attr_info(self):
        self.scanned_attr_info = True

        self.attr_info = {}
        self.attr_list = []
        self.class_attr_list = []

        # Port classes are usually uninteresting to the end-user, so
        # they are not explicitly documented. Instead, attributes of
        # port classes are documented as attributes of the parent class.
        # E.g., if port class X.Y has an attribute Z, and class X registers
        # X.Y as ports named 'port.y[0]' and 'port.y[1]', then the attribute
        # is documented as an attribute of device X, with names y[0].Z
        # and y[1].Z.
        #
        # If you register a port with non-port class, then that class
        # should have standalone documentation and the attributes do not
        # need to be documented.
        #
        # It is possible to register a port of a port-class belonging
        # to a different class, i.e. X registers port P of class Y.Z.
        # This is a strange thing to do, and attributes of Y.Z will
        # currently not be documented in this case.
        #
        # classname: prefixes
        classes = {self.name: ['']}
        for (port_prefix, pclass) in VT_get_port_classes(self.name).items():
            if pclass.startswith(self.name + '.'):
                classes.setdefault(pclass, []).append(port_prefix + '.')
        for cls in classes:
            port_prefixes = sorted(classes[cls])
            classname_prefix = ('' if cls == self.name
                                else cls[len(self.name) + 1:] + '.')
            # gather attribute information
            ati = simics.VT_get_all_attributes(cls)
            for a in ati:
                # select attributes at this point
                attr_attr = a[2]
                if (self.online
                    or ((attr_attr & Sim_Attr_Internal) == 0
                        or (attr_attr & Sim_Attr_Flag_Mask) == Sim_Attr_Required)):
                    attr_i = AttrDesc()
                    name = a[0]
                    attr_i.name = a[0]
                    attr_i.port_prefixes = port_prefixes
                    attr_i.rw = a[1]
                    attr_i.attributes = a[2]
                    attr_i.description = a[3]
                    if not attr_i.description:
                        self.verbosePrint(
                            "ClassDesc() *** no description for attribute "
                            + cls + "." + name)
                    attr_i.type = a[4]
                    attr_i.indexed_type = a[5]
                    if not attr_i.type and not attr_i.indexed_type:
                        self.verbosePrint(
                            "ClassDesc() *** no type for attribute "
                            + cls + "." + name)
                    self.attr_info[classname_prefix + name] = attr_i
                    if not (attr_attr & Sim_Attr_Internal):
                        self.verbosePrint("ClassDesc():     attribute " + name)
                        if attr_i.attributes & Sim_Attr_Class:
                            # The class_desc attribute is automatically
                            # registered identically on all classes,
                            # and therefore of no interest
                            if name != 'class_desc':
                                self.class_attr_list.append(
                                    classname_prefix + name)
                        else:
                            self.attr_list.append(classname_prefix + name)

        if self.class_attr_list:
            self.class_attr_list.sort()
        if self.attr_list:
            self.attr_list.sort()

    def updateInterfaces(self, ifc_list):
        '''Update ifc_list, which is a dict name->IfcDesc, to include
        interfaces and port interfaces of this class. Also update
        IfcDesc objects to include self among implementing classes.
        '''
        port_ifcs = {iface for (_, ifaces, _)
                     in self.port_ifaces.values()
                     for iface in ifaces}
        for ifc in self.ifc_list + list(port_ifcs):
            if ifc in ifc_list:
                ifcd = ifc_list[ifc]
            else:
                ifcd = IfcDesc(ifc, verbose=self.verbose)
                ifc_list[ifc] = ifcd

            self.verbosePrint("ClassDesc::updateInterfaces():     interface " + ifc)
            ifcd.classes.append(self.name)

    def printConnectors(self, o):
        if 'component' in self.ifc_list:
            import comp_info
            try:
                info = comp_info.get_comp_info(SIM_get_class(self.name).name)
                connectors = info['connectors']
            except (comp_info.CompInfoAttribute, comp_info.CompInfoCreate) as msg:
                print("error %s" % msg)
                return
            connectors = group_connector_info(connectors)
            if connectors:
                o.beginDocItem('Connectors')

                cnt = [None] * 3
                cnt[0] = [x for x in connectors if
                          connectors[x]['direction'] == 'up']
                cnt[1] = [x for x in connectors if
                          connectors[x]['direction'] == 'down']
                cnt[2] = [x for x in connectors if
                          connectors[x]['direction'] == 'any']

                if self.online:
                    # we can't use a table here, as the terminal won't know
                    # what to do with it
                    for c in cnt:
                        for a in sorted(c):
                            o.pn("<b>" + a + "</b>, type: "
                                 + connectors[a]['type'] + ", direction: "
                                 + connectors[a]['direction'])
                else:
                    o.pn("")
                    o.pn("")
                    o.beginTable(len(connectors), border = "true")
                    o.beginRow()
                    o.pr(o.makeCell('<b>Name</b>')
                         + o.makeCell('<b>Type</b>')
                         + o.makeCell('<b>Direction</b>'))
                    o.endRow()
                    for c in cnt:
                        for a in sorted(c):
                            o.beginRow()
                            o.pr(o.makeCell(a)
                                 + o.makeCell(connectors[a]['type'])
                                 + o.makeCell(connectors[a]['direction']))
                            o.endRow()
                    o.endTable()
                o.endDocItem()

    def printLong(self, o, doc, no_extern_link = 0, online = 0,
                  iface_links = True):
        ifc_list = doc.ifaces
        id = classId(self.name)

        o.beginAdd(id, id, o.encode(self.name), 'Class')
        o.pr(o.makeIndex([self.name]))
        o.beginDoc()

        aliases = [alias for alias, cname in simics.CORE_get_all_class_aliases()
                   if cname == self.name]
        if aliases:
            o.beginDocItem('Aliases')
            o.printListWithSep(sorted(aliases), None,
                               o.encode, "", "", ", ")
            o.endDocItem()

        # Description
        o.beginDocItem('description')
        if o.supports_insert():
            o.pr('<insert id=' + o.q(id + "_desc") + '/>')
        else:
            o.pr(self.description)
        o.endDocItem()

        # Interfaces
        o.beginDocItem('Interfaces Implemented')
        if self.ifc_list:
            def ifc_id(i):
                ifc = ifc_list.get(i)
                return (ifcId(ifc.name)
                        if ifc and not no_extern_link and iface_links
                        else None)
            o.printListWithSep(sorted(self.ifc_list), ifc_id,
                               o.encode, "", "", ", ")
        else:
            o.pr('None')
        o.endDocItem()

        # Port Objects
        port_classes = VT_get_port_classes(self.name)
        if port_classes:
            o.beginDocItem('Port Objects')
            port_arrays = {}
            for (pname, pclass) in port_classes.items():
                cls = SIM_get_class(pclass)
                desc = simics.VT_get_port_obj_desc(self.name, pname)
                if desc is None:
                    desc = cls.class_desc or ""
                if desc:
                    desc = " : " + desc
                if "." in pclass:
                    ifaces = sorted(simics.VT_get_class_info(pclass)[2])
                    for x in ('conf_object', 'log_object'):
                        if x in ifaces:
                            ifaces.remove(x)
                    if ifaces:
                        kind_str = "({})".format(", ".join(ifaces))
                    else:
                        kind_str = ""
                else:
                    if pclass == "namespace":
                        continue
                    kind_str = "&lt;{}&gt;".format(pclass)
                (port_fmt, indices) = extract_indices(pname)
                port_arrays.setdefault(port_fmt, []).append(
                    (indices, pname, kind_str + desc))
            port_rows = []
            # If a port object array has the regular format (zero
            # indexed, fully populated, homogeneous), then print the
            # entire array on one row, with "0..N" to denote indices.
            # If the port array is somehow irregular, then keep it
            # expanded with one row for each port instance.
            for (port_fmt, instances) in port_arrays.items():
                array_sizes = is_cartesian_product(
                    coord for (coord, _, _) in instances)
                descs = set(desc for (_, _, desc) in instances)
                if array_sizes is not False and len(descs) == 1:
                    # homogeneous (possibly multi-dimensional) port array:
                    # output a single entry indexed by [0..size-1] index
                    [desc] = descs
                    port_rows.append((
                        port_fmt.format(*('0..%d' % (sz - 1,)
                                          for sz in array_sizes)),
                        desc))
                else:
                    # heterogeneous array of port objects
                    port_rows.extend((pname, desc)
                                     for (_, pname, desc) in instances)
            port_rows = sorted('<b>{}</b> {}'.format(pname, desc)
                               for (pname, desc) in port_rows)
            o.printListWithSep(port_rows, None, lambda x: x, "", "", "<br/>")
            o.endDocItem()

        if self.port_ifaces:
            # Use "Port Interfaces" for now, reserving the name "Ports" for the
            # upcoming port objects
            o.beginDocItem('Port Interfaces')

            def iface_text(iface):
                if iface in ifc_list and not no_extern_link and iface_links:
                    return o.makeLink(ifcId(iface), o.encode(iface))
                else:
                    return o.encode(iface)

            port_list = [
                '%s (%s) : %s'
                % (o.encode(port + ''.join('[%d]' % (n,) for n in sizes)),
                   ', '.join(map(iface_text, sorted(ifaces))), desc)
                for (port, (sizes, ifaces, desc)) in sorted(
                        self.port_ifaces.items())]

            o.printListWithSep(port_list, None, lambda x: x, "", "", "<br/>")
            o.endDocItem()

        notifiers = simics.CORE_get_class_notifiers(self.name, False)
        # To make output shorter we print the Notifiers section only when there
        # is something to report. notifiers list is already sorted.
        if notifiers:
            o.beginDocItem('Notifiers')
            o.printListWithSep(notifiers, None,
                               o.encode, "", "", ", ")
            o.endDocItem()

        # print Connectors, if any
        self.printConnectors(o)

        # Modules (not of large importance: let's print this last)
        o.beginDocItem('Provided By')
        module = get_module_encode(o, online)(self.module)
        o.pn(module if no_extern_link
             else o.makeLink(moduleId(self.module), module))
        o.endDocItem()

        o.endDoc()

        # compute how many attributes there are
        if len(self.attr_list):
            o.printSection("false", id + "_attributes")

        if len(self.class_attr_list):
            o.printSection("false", id + "_class_attributes")

        # compute how many commands there are
        cmd_nb = 0
        for i in self.ifc_list:
            cmd_nb = cmd_nb + len(ifc_list[i].commands)
        cmd_nb = cmd_nb + len(self.commands)

        if cmd_nb:
            o.printSection("false", id + "_commands")

        o.endAdd()

        if o.supports_insert():
            o.beginAdd(id + "_desc", "", "")
            o.pn(self.description)
            o.endAdd()

    def printSingleAttribute(self, o, doc, a, online = 0, no_extern_link = 0):
        attr = self.attr_info[a]

        internal_attr = attr.attributes & Sim_Attr_Internal
        o.beginDList()
        if internal_attr:
            o.pr(o.makeDListTitle(('&lt;%s&gt;.<attr>%s</attr>'
                                   + ' is an <b>Internal</b> attribute') % (
                        self.name, attr.name)))
            o.pn(o.makeTarget(attrId(self.name, a)))
        elif online:
            o.pr(o.makeDListTitle(('<i>Attribute &lt;%s&gt;.'
                                   '<b><attr>%s</attr></b></i>') % (
                        self.name, attr.name)))
            o.pr('<br/>\n')
        else:
            # Similar to when presenting port-arrays under a class, we will
            # collapse the ports that are part regular arrays into one shorthand
            # index ("[X..Y]")

            port_arrays = {}
            for prefix in attr.port_prefixes:
                (port_fmt, indices) = extract_indices(prefix)
                port_arrays.setdefault(port_fmt, []).append(indices)
            port_prefixes = []
            for (port_fmt, indices) in port_arrays.items():
                array_sizes = is_cartesian_product(indices)
                if array_sizes is not False:
                    port_prefixes.append(
                        port_fmt.format(*('0..%d' % (sz - 1,)
                                          for sz in array_sizes)))
                else:
                    for i in indices:
                        port_prefixes.append(
                            port_fmt.format(*('%d' % (sz)
                                              for sz in i)))
            o.pr(o.makeDListTitle('<attr>' + ', '.join(
                [prefix + attr.name
                 for prefix in port_prefixes]) + '</attr>'))
            o.pn(o.makeTarget(attrId(self.name, a)))

        o.beginDListItem()

        chkp_type       = attr.attributes & Sim_Attr_Flag_Mask
        class_attr      = attr.attributes & Sim_Attr_Class

        integer_indexed = attr.attributes & Sim_Attr_Integer_Indexed
        string_indexed  = attr.attributes & Sim_Attr_String_Indexed
        list_indexed    = attr.attributes & Sim_Attr_List_Indexed
        persistent      = attr.attributes & Sim_Attr_Persistent

        if chkp_type == 0:
            o.pr('<b>Required</b> ')
        elif chkp_type == 1:
            o.pr('<b>Optional</b> ')
        elif chkp_type == 3:
            o.pr('<b>Session</b> ')
        elif chkp_type == 4:
            o.pr('<b>Pseudo</b> ')
        else:
            o.pr('<todo>No checkpoint type</todo>')

        if internal_attr:
            o.pr('<b>internal</b> ')
        if class_attr:
            o.pr('<b>class</b> ')

        o.pr('attribute; ')
        if attr.rw == 3:
            o.pr('<b>read/write</b> ')
        elif attr.rw & 1:
            o.pr('<b>read-only</b> ')
        else:
            o.pr('<b>write-only</b> ')
        o.pr('access')
        if not attr.type and not attr.indexed_type:
            o.pr('; type: <b>unknown type</b>')
        elif attr.type:
            o.pr('; type: ' + type_encode(attr.type))

        if integer_indexed or string_indexed or list_indexed:
            o.pr('; ')
            index_list = []
            if integer_indexed:
                index_list.append("integer")
            if string_indexed:
                index_list.append("string")
            if list_indexed:
                index_list.append("list")
            o.printListWithSep(index_list, None, lambda x: x,
                               "<b>", "</b>", " or ")
            o.pr(' indexed; ')
            if attr.indexed_type:
                o.pr(' indexed type: ' + type_encode(attr.indexed_type))
            else:
                o.pr(' indexed type: <b>unknown type</b>')

        if persistent:
            o.pr('; <b>persistent</b> attribute')

        o.pn('.')

        if attr.description:
            o.pr(attr.description)
        o.endDListItem()
        o.endDList()

    def printAttributes(self, o, doc, class_attr = 0, extended = 1,
                        no_extern_link = 0):
        #
        # Attributes
        #
        id = classId(self.name)
        if class_attr:
            o.beginAdd(id + '_class_attributes', '', 'Class Attributes')
            attr_list = self.class_attr_list
        else:
            o.beginAdd(id + '_attributes', '', 'Attributes')
            attr_list = self.attr_list

        # just a summary of attributes?
        if not attr_list:
            o.pn('none')
        elif not extended:
            # define a function for attribute links
            def attrClassId(a):
                return attrId(self.name, a)
            o.printListWithSep(attr_list,
                               None if no_extern_link else attrClassId,
                               o.encode, "<attr>", "</attr>", ", ")
        else:
            # Attributes description
            for a in attr_list:
                self.printSingleAttribute(o, doc, a,
                                          no_extern_link = no_extern_link)

        o.endAdd()

    def printCommands(self, o, doc, no_extern_link = 0, iface_links = True):
        #
        # Command list
        #
        ifc_list = doc.ifaces
        cmd_list = doc.commands

        # compute how many commands there are
        id = classId(self.name)

        cmd_nb = 0
        for i in self.ifc_list:
            cmd_nb = cmd_nb + len(ifc_list[i].commands)
        cmd_nb = cmd_nb + len(self.commands)

        if cmd_nb:
            o.beginAdd(id + "_commands", "", 'Command List')
            o.beginDoc()

            # Commands inherited from interfaces
            for i in sorted(self.ifc_list):
                ifc = ifc_list[i]
                ifc_c = sorted(ifc.commands.keys())

                def stripAndEncodeCmd(c):
                    return o.encode(stripCommandName(c))

                def ifc_id(i):
                    if i in ifc_list and not no_extern_link and iface_links:
                        return o.makeLink(ifcId(i), i)
                    else:
                        return i

                def command_id(c):
                    if no_extern_link or c not in cmd_list:
                        return None
                    else:
                        return commandId(c)

                if ifc_c:
                    o.beginDocItem('Commands defined by interface '
                                   + ifc_id(i))
                    o.printListWithSep(ifc_c,
                                       command_id,
                                       stripAndEncodeCmd,
                                       "", "", ", ")
                    o.endDocItem()

            # Short command description
            cmd_list = sorted(self.commands.keys())
            if cmd_list:
                o.beginDocItem('Commands')
                o.beginTable(len(cmd_list))
                sz = 20
                for c in cmd_list:
                    sz = max(sz, len(stripCommandName(c)) + 1)
                for c in cmd_list:
                    o.beginRow()
                    o.pr(o.makeCell('<cmd>'
                                    + o.makeLink(commandId(c),
                                                 o.encode(stripCommandName(c)))
                                    + '</cmd>', size=sz))
                    o.beginCell()
                    if self.commands[c].cmd.is_deprecated():
                        o.pr('<i>deprecated</i> &mdash; ')
                    o.pr(self.commands[c].cmd.short)
                    o.endCell()
                    o.endRow()
                o.endTable()
                o.endDocItem()

            o.endDoc()
            o.endAdd()

    def printComponent(self, o, doc, no_extern_link = 0):
        #
        # Formatted output for component info in target guide
        #
        id = componentId(self.name)

        o.beginAdd(id, id, o.encode(self.name), 'Component')
        o.pr(o.makeIndex([self.name]))
        o.beginDoc()

        # Description
        o.beginDocItem('description')
        o.pr(self.description)
        o.endDocItem()

        def cmpCmdEncode(cmp_name):
            return cmp_name.replace('_', '-')

        if self.name not in ('component', 'top-component'):
            o.beginDocItem('Commands')
            o.pn('<insert nowarning="true" id=' + o.q("__rm_gcmd_create-"
                                     + labelEncode(cmpCmdEncode(self.name)))
                 + '/>')
            o.pn('<insert nowarning="true" id='
                 + o.q("__rm_gcmd_new-" + labelEncode(cmpCmdEncode(self.name)))
                 + '/>')
            o.endDocItem()

        if self.attr_list:
            o.beginDocItem('Attributes')
            o.beginDList()
            for a in self.attr_list:
                info = self.attr_info[a]
                o.pr(o.makeDListTitle(info.name))
                o.beginDListItem()
                o.pr(info.description)
                o.endDListItem()
            o.endDList()
            o.endDocItem()

        # Connectors
        self.printConnectors(o)

        o.endDoc()
        o.endAdd()

class ClassNotLoadedDesc(GenericDesc):
    def __init__(self, name):
        self.name = name
        self.modules = simics.VT_get_all_implementing_modules(name)

    def printLong(self, o, online = 0):
        o.beginAdd(id, id, o.encode(self.name), 'Class')
        o.pr(o.makeIndex([self.name]))
        o.beginDoc()

        if self.modules:
            # Modules
            o.beginDocItem('Description')
            if len(self.modules) == 1:
                help_msg = ("load the {0} module (this can be done by running"
                            " the 'load-module {0}' Simics CLI command)".format(
                                self.modules[0]))
            else:
                help_msg = 'load one of the modules above'
            o.pn('This class has not been loaded into Simics yet.'
                 ' To access its documentation, %s.' % (help_msg,))
            o.endDocItem()

            o.beginDocItem('Provided By')
            o.printListWithSep(self.modules, None, o.encode, "", "", ", ")
            o.endDocItem()
        else:
            o.pn('Unknown class.')

        o.endDoc()
        o.endAdd()

class AttrDesc(GenericDesc):
    def __init__(self):
        self.name = ""
        self.rw = 0
        self.attributes = 0
        self.description = ""
        self.type = ""
        self.indexed_type = ""


# There are 3 categories of interfaces:
# - undocumented interfaces delivered in this package
# - documented interfaces delivered in this package
# - interfaces not delivered in this package
# The class documentation should list all interfaces, but
# the reference manual will only include documentation for interfaces
# delivered in the package.
@total_ordering
class IfcDesc(GenericDesc):
    def __init__(self, name, documented=False, defined_here=False,
                 verbose=False):
        self.verbose = verbose
        self.name = name
        # For documented interfaces, this is "<insert id=.../>"
        self.description = ("<insert id=\"%s_interface_t\"/>" % (name,)
                            if documented else "")
        self.commands = {}
        self.classes = []
        # If true, then the interface is documented by the package we
        # are documenting.
        self.defined_here = defined_here

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return self.name < other.name

    def __hash__(self):
        return hash(self.name)

    def printLong(self, o, doc, online = 0, no_extern_link = 0):
        id = ifcId(self.name)
        o.beginAdd(id, id, o.encode(self.name), 'Interface')
        # Currently interface online help is empty. Maybe we should
        # fall back to api-help-description instead?
        if not online:
            assert self.description
            o.pr(o.makeIndex([self.name]))
            ifcType = self.name + "_interface_t"
            o.pr(o.makeIndex([ifcType]))

            o.beginDoc()

            o.beginDocItem('description')
            o.pn(self.description)
            o.endDocItem()
            o.beginDocItem('exec-context')
            o.pn('<insert id="%s_interface_exec_context"/>'
                 % (o.encode(self.name),))
            o.endDocItem()
            o.endDoc()
        o.endAdd()

class HapDesc(GenericDesc):
    def __init__(self, verbose):
        self.verbose = verbose
        self.name = ""
        self.param_types = ""
        self.param_names = []
        self.index = ""
        self.help = ""
        self.modules = []

    def printLong(self, o, doc, no_extern_link = 0,
                  online = 0, include_modules = True):
        o.beginAdd(hapId(self.name), hapId(self.name), o.encode(self.name),
                   'Hap')
        o.pr(o.makeIndex([self.name]))
        o.beginDoc()

        o.beginDocItem('description')
        o.pr('  ' + self.help.strip())
        o.endDocItem()

        o.beginDocItem('Callback Type')
        pnames = ["callback_data", "trigger_obj"]
        if self.param_names:
            pnames = pnames + self.param_names
        o.pn('    <pre>%s</pre>' % hap_c_arguments("noc" + self.param_types,
                                                   pnames))
        o.endDocItem()

        if self.index:
            o.beginDocItem('Index')
            o.pr(self.index)
            o.endDocItem()

        # Module (not of large importance: let's print this last)
        if include_modules:
            o.beginDocItem('Provided By')
            o.printListWithSep(
                self.modules, None if no_extern_link else moduleId,
                get_module_encode(o, online), "", "", ", ")
            o.endDocItem()

        o.endDoc()
        o.endAdd()

class NotifierDesc(GenericDesc):
    def __init__(self, verbose):
        self.verbose = verbose
        self.name = ""
        self.identifier = -1
        self.is_global = False
        self.description = ""
        self.cls_desc_list = []  # ((class, description),...)

    def printLong(self, o, doc, no_extern_link = 0, online = 0):
        o.beginAdd(notifierId(self.name), notifierId(self.name),
                   o.encode(self.name), 'Notifier')
        o.pr(o.makeIndex([self.name]))
        o.beginDoc()

        info = {}  # map description to list of classes
        for (cls_name, desc) in self.cls_desc_list:
            info.setdefault(desc, []).append(cls_name)

        if self.is_global:
            o.beginDocItem('description')
            o.pr(self.description)
            o.endDocItem()
        else:
            for desc in sorted(info):
                o.beginDocItem('description')
                o.pr(desc)
                o.endDocItem()
                o.beginDocItem('Classes')
                if self.identifier in (simics.Sim_Notify_Queue_Change,
                                       simics.Sim_Notify_Cell_Change,
                                       simics.Sim_Notify_Object_Delete):
                    o.pr("all classes")
                else:
                    o.printListWithSep(sorted(info[desc]), None,
                                       o.encode, "", "", ", ")
                o.endDocItem()

        o.endDoc()
        o.endAdd()

#
# Gathering documentation
#

class DocException(Exception): pass

def build_module_dict(verbose, module_names=None):
    '''Return a dict mapping module name to ModuleDesc object.  The set of
    keys is given by module_names, or if module_names=None, the
    currently loaded modules.'''

    module_list = SIM_get_all_modules()
    all_modules = {m[0]: m for m in module_list}
    if module_names is None:
        # populate module_names with all currently loaded modules
        module_names = [core_module] + [m[0] for m in module_list if m[2]]
    else:
        failed_modules = []
        for m in module_names:
            if m != core_module:
                try:
                    simics.SIM_load_module(m)
                except simics.SimExc_General:
                    failed_modules.append(m)
        if failed_modules:
            if os.environ.get('SKIP_MISSING_MODULES'):
                print(('*** Failed to load modules: '
                                     + ' '.join(failed_modules)), file=sys.stderr)
                module_names = set(module_names).difference(failed_modules)
            else:
                raise DocException('Failed to load modules %s, required'
                                     % ' '.join(failed_modules)
                                     + ' to build reference manual. Set'
                                     + ' SKIP_MISSING_MODULES to build with'
                                     + ' missing modules excluded.')

    # map non-port class to list of port classes
    class_ports = {}
    all_classes = SIM_get_all_classes()
    for c in all_classes:
        if '.' in c:
            class_ports.setdefault(c.split('.', 1)[0], []).append(c)
    module_dict = {}
    all_module_classes = {c for m in all_modules.values()
                      for c in m[7]}
    core_classes = [c for c in all_classes
                    if '.' not in c and c not in all_module_classes]
    for m in module_names:
        if m == core_module:
            module_dict[m] = ModuleDesc(verbose, core_module,
                                        core_module_file, core_classes,
                                        [pc for c in core_classes
                                         for pc in class_ports.get(c, [])])
        else:
            filename = all_modules[m][1]
            classes = all_modules[m][7]
            module_dict[m] = ModuleDesc(verbose, m, filename, classes,
                                        [pc for c in classes
                                         for pc in class_ports.get(c, [])])

    return module_dict


# Build a complete class list and return it
# Needs a ready module list to update, build an interface list at the same time
def build_class_and_ifc_list(verbose, online, module_dict, ifc_list):
    class_list = {}
    if online:
        all_classes = set(SIM_get_all_classes())

    for m in module_dict.values():
        if online:
            # We have not decided yet (SIMICS-8526) how port object
            # classes should be documented in reference manuals but for
            # online help we include information about them.
            classes = itertools.chain(m.classes, m.port_classes)
        else:
            classes = m.classes
        for c in classes:
            if online and c not in all_classes:
                continue  # Forgive missing class when building online help.
            cd = ClassDesc(verbose, online, c, m.name)
            if verbose:
                print("build_class_list(): adding class", cd.name)
            class_list[cd.name] = cd
            cd.updateInterfaces(ifc_list)

    return (class_list, ifc_list)

def build_command_desc(class_list, ifc_list, module_dict, cmd,
                       verbose, online):
    command_desc = CmdDesc(True, cmd.name, cmd)

    module = cmd.module or core_module
    command_desc.module = module
    if module not in module_dict:
        if online:
            # there should be no registered commands on non-loaded classes
            if cmd.cls:
                simics.pr_err(f"Error: {module} is not loaded"
                              " but has registered commands")
            # command defined on startup, but module is not loaded,
            # document it with a non-loaded module
            command_desc.module += " (not loaded)"
            return (True, command_desc)
        return (False, command_desc)
    if cmd.cls:
        if verbose:
            print("build_command_list(): adding command %s to class %s" % (
                cmd.name, cmd.cls))
        if cmd.cls not in class_list and '.' not in cmd.cls:
            # if a class command is defined in module m, then it
            # should be defined on a class provided by m.  It's
            # possible to add commands to classes defined by other
            # modules; if this happens in practice and makes sense,
            # then we need to handle this case with more logic (like
            # verifying that the class is documented)
            msg = ('Error: command %s defined by %s on class %s,'
                   % (cmd.name, module, cmd.cls)
                   + ' not provided by ' + module)
            if online:
                simics.pr_err(msg)
                return (False, command_desc)
            else:
                raise DocException(msg)
        if '.' not in cmd.cls:
            # class command
            class_list[cmd.cls].commands[cmd.name] = command_desc

    elif cmd.iface:
        if cmd.iface in ifc_list:
            # interface command
            ifc_list[cmd.iface].commands[cmd.name] = command_desc
            if verbose:
                print("build_command_list(): adding command %s to interface %s" % (
                    cmd.name, cmd.iface))
        else:
            # interface defined elsewhere
            if verbose:
                print(("build_command_list(): *** unknown namespace "
                       + cmd.iface + " for command " + cmd.name))
    else:
        # module command
        module_dict[module].commands[cmd.name] = command_desc
        if verbose:
            print("build_command_list(): adding command %s to module %s" % (
                cmd.name, module))

    return (True, command_desc)

def alias_name(alias, cmd):
    return cli_command(method=alias, cls=cmd.cls, iface=cmd.iface).name

# Build a command list and update class/ifc/module
def build_command_list(verbose, online, deprecated,
                       module_dict, class_list, ifc_list):
    command_list = {}
    alias_list = {}
    groups = {}
    avoided_command_list = {}
    doc_with_list = {}

    cmd_list = simics_commands()
    for cmd in cmd_list:
        # doc_with - update the list of commands documented together
        if cmd.doc_with:
            doc_with_list.setdefault(cmd.doc_with, []).append(cmd.name)

        (add_to_list, command_desc) = build_command_desc(
            class_list, ifc_list, module_dict, cmd, verbose, online)

        # complete info and add command to list
        if add_to_list:
            if (cmd.type and isinstance([], type(cmd.type))
                and (not cmd.is_deprecated() or deprecated)):
                for t in cmd.type:
                    if t in groups:
                        groups[t].append(cmd)
                    else:
                        groups[t] = [cmd]

            for alias in cmd.alias:
                alias_list[alias_name(alias, cmd)] = command_desc

            command_list[cmd.name] = command_desc
        else:
            avoided_command_list[cmd.name] = command_desc

    for c in doc_with_list:
        if c in command_list:
            command_list[c].doc_with_list = doc_with_list[c]
        elif c in avoided_command_list:
            avoided_command_list[c].doc_with_list = doc_with_list[c]

    return (command_list, avoided_command_list, alias_list, groups)

# build a hap list and update the core module on the hap it defined
def build_hap_list(verbose, module_dict):

    hap_list = {}
    haps = conf.sim.hap_list

    for (name, params, param_names, index, description, *_) in haps:
        hd = HapDesc(verbose)
        hd.name = name
        hd.param_types = params
        hd.param_names = param_names
        hd.index = index
        hd.help = description
        hd.modules = []
        hap_list[hd.name] = hd

    for m in module_dict.values():
        for h in m.haps:
            hap_list[h].modules.append(m.name)

    for h in hap_list.values():
        if not h.modules and core_module in module_dict:
            h.modules = [core_module]
            module_dict[core_module].haps.append(h.name)

    return hap_list

def build_notifiers_dict(verbose):

    notifiers_dict = {}
    # Notifiers format:
    # ((name, identifier, is_global, ((class, description),...)),...)
    notifiers = conf.sim.attr.notifier_list
    for (name, identifier, global_desc, cls_desc_list) in notifiers:
        nd = NotifierDesc(verbose)
        nd.name = name
        nd.identifier = identifier
        nd.description = global_desc
        nd.is_global = global_desc is not None
        nd.cls_desc_list = cls_desc_list
        notifiers_dict[nd.name] = nd

    return notifiers_dict

class ManualContents:
    '''The modules, interfaces and classes that define the contents of a
    manual'''
    def __init__(self, modules, ifaces, classes, commands, avoided_commands,
                 command_aliases, command_categories, haps, notifiers):
        # {name: ModuleDesc}. All modules to document. Core modules
        # use core_module as name.
        self.modules = modules
        # {name: IfcDesc}. Interfaces whose documentation should be
        # included in this manual. Also includes interfaces that are
        # implemented by documented classes, but whose documentation belong
        # to a different manual, and interfaces that lack documentation.
        self.ifaces = ifaces
        # {name: ClassDesc}. All classes defined by ModuleDesc.
        self.classes = classes
        # {name: CmdDesc}. All commands to document, i.e., commands
        # defined by modules in self.modules. For namespaced commands,
        # the name is "<ns>.cmd".
        self.commands = commands
        # {name: CmdDesc}. All commands that don't belong to self.commands.
        self.avoided_commands = commands
        # {name: CmdDesc}. Command aliases to document. CmdDesc
        # instances are shared with the original command in
        # self.commands.
        self.command_aliases = command_aliases
        # {name: [CmdDesc]}. Command categories to document. CmdDesc
        # instances all belong to self.commands.
        self.command_categories = command_categories
        # {name: HapDesc}. Haps to document.
        self.haps = haps
        # {name: NotifierDesc}. Notifiers to document.
        self.notifiers = notifiers

def DOC_gather_documentation(
        verbose = False,
        online = False,  # True if documentation will be used by the help
                         # command, False if documentation is for manuals
        module_names = None,
        ifaces = None,
        include_deprecated = True):

    modules = build_module_dict(verbose, module_names)
    (classes, ifaces) = build_class_and_ifc_list(
        verbose, online, modules, ifaces or {})

    (cmds, avoided_cmds, aliases, categories) = build_command_list(
        verbose, online, include_deprecated, modules, classes, ifaces)

    haps = build_hap_list(verbose, modules)
    notifiers = build_notifiers_dict(verbose)

    return ManualContents(modules, ifaces, classes, cmds, avoided_cmds,
                          aliases, categories, haps, notifiers)

#
# Reference manual
#

# print the command descriptions into one section
def print_command_descriptions(o, doc, cmds, prefix, sec_id, sec_name,
                               no_extern_link):
    for c in cmds:
        c.printLong(o, doc, prefix + labelEncode(c.name),
                    no_extern_link = no_extern_link)

    o.pn('<add id="%s">' % sec_id)
    o.pn('<name>%s</name>' % sec_name)
    for c in cmds:
        o.pn('<insert id=' + o.q(prefix + labelEncode(c.name)) + '/>')
    o.pn('</add>')
    o.pn('')
    return cmds

# print the command chapter in reference manual
def print_command_chapter(o, doc, no_extern_link = 0):
    # Now add the command type documentation
    groups = doc.command_categories

    def format_command_ref(e):
        assert ((doc.commands[e].module or core_module)
                in doc.modules)
        if no_extern_link:
            return o.encode(e)
        else:
            return '<nref label="%s">%s</nref>' % (commandId(e), o.encode(e))

    for g in sorted(groups):
        o.pn('<add id=' + o.q('__rm_command_group_' + g) + '>')
        o.pn('<name>' + g + '</name>')
        o.pn('<table>')
        for c in sorted(groups[g], key=sort_key_cmd):
            o.pn('<tr><td>')
            o.pn('  ' + format_command_ref(c.name))
            o.pr('</td><td>')
            if c.is_deprecated():
                o.pr('<i>deprecated</i> &mdash; ')
            o.pn(c.short + '</td></tr>')
        o.pn('</table>')
        o.pn('</add>')

    # section for categories
    o.pn('<add id="__rm_command_categories">')
    o.pn('<name>List by Categories</name>')
    o.pn('')
    for g in sorted(groups):
        o.pn('<section numbering="false" id='
           + o.q('__rm_command_group_' + g) + '/>')
    o.pn('</add>')

    # complete command list
    o.pn('<add id="__rm_command_complete_list">')
    o.pn('<name>Complete List</name>')
    o.pn('')
    o.pn('<table>')

    # add all aliases to the list
    ccmd = {}
    for c in doc.commands.values():
        deprecated = ('<i>deprecated</i> &mdash; '
                      if c.cmd.is_deprecated() else '')
        ccmd[c.cmd.name] = ('<tr><td>%s</td><td>%s %s</td></tr>'
                       % (format_command_ref(c.cmd.name), deprecated,
                          c.cmd.short))
        for a in c.cmd.alias:
            name = alias_name(a, c.cmd)
            ccmd[name] = '<tr><td>%s</td><td>%salias for %s</td></tr>' % (
                o.encode(name), deprecated, format_command_ref(c.cmd.name))
    for name in sorted(ccmd, key=str.lower):
        o.pn(ccmd[name])

    o.pn('</table>')
    o.pn('</add>')
    o.pn('')

    (gcmd, scmd, icmd) = ([], [], [])
    for (_, c) in sorted(doc.commands.items()):
        assert (c.cmd.module or core_module) in doc.modules
        if c.cmd.cls:
            scmd.append(c)
        elif c.cmd.iface:
            icmd.append(c)
        else:
            gcmd.append(c)

    # commands descriptions
    print_command_descriptions(o, doc, gcmd, '__rm_gcmd_',
                               '__rm_global_command', 'Global Commands',
                               no_extern_link)
    print_command_descriptions(o, doc, scmd, '__rm_scmd_',
                               '__rm_class_command',
                               'Namespace Commands by Class',
                               no_extern_link)
    print_command_descriptions(o, doc, icmd, '__rm_icmd_',
                               '__rm_interface_command',
                               'Namespace Commands by Interface',
                               no_extern_link)

    o.pn('<add id="__rm_command_list">')
    o.pn('<name>Commands</name>')
    o.pn('')
    if doc.commands:
        o.pn('<section id="__rm_command_complete_list"/>')
        o.pn('<section id="__rm_command_categories"/>')
        if gcmd:
            o.pn('<section id="__rm_global_command"/>')
        if scmd:
            o.pn('<section id="__rm_class_command"/>')
        if icmd:
            o.pn('<section id="__rm_interface_command"/>')
    else:
        o.pn('No commands were defined in this package.')
    o.pn('')
    o.pn('</add>')

def print_reference_manual(filename, doc, include_commands, include_haps,
                           include_modules,
                           no_extern_link = 0, modules_with_source = [],
                           include_interfaces = True):
    o = JdocuOutputHandler(filename)

    def sorry_nothing_in_this_chapter(stuff, name_of_stuff):
        if len(stuff) == 0:
            o.pn('No %s were defined in this package.' % name_of_stuff)

    module_dict = doc.modules
    class_list = doc.classes
    ifc_list = doc.ifaces
    hap_list = doc.haps

    o.pn('/*')
    o.pn('')

    if include_commands:
        # commands - the case where no commands are defined is handled in
        # print_command_chapter()
        print_command_chapter(o, doc, no_extern_link = no_extern_link)

    # modules
    if include_modules:
        modules = sorted(module_dict.values(), key=sort_key_item)

        o.pn('<add id="__rm_module_list">')
        o.pn('<name>Modules</name>')
        o.pn('')

        ms = ['<module>%s</module>' % (m.name,)
              for m in modules if m.name in modules_with_source]
        if ms:
            if len(ms) > 1:
                ms[-1] = 'and ' + ms[-1]
            o.pn('If you have Simics Model Builder product, it includes full'
                 + ' source code for the following modules:')
            o.pn('')
            o.pn(', '.join(ms) + '.')

        for m in modules:
            m.printLong(o, doc, no_extern_link = no_extern_link,
                        include_haps = include_haps)
        sorry_nothing_in_this_chapter(modules, 'modules')
        o.pn('')
        o.pn('</add>')

    # classes
    classes = sorted(class_list.values(), key=sort_key_item)

    component_list = [x for x in classes if "component" in x.ifc_list]
    class_list = [x for x in classes if "component" not in x.ifc_list]

    for c in class_list:
        c.printLong(o, doc, no_extern_link = no_extern_link,
                    iface_links = include_interfaces)
        c.printAttributes(o, doc, class_attr = True,
                          no_extern_link = no_extern_link)
        c.printAttributes(o, doc, class_attr = False,
                          no_extern_link = no_extern_link)
        c.printCommands(o, doc, no_extern_link = no_extern_link,
                        iface_links = include_interfaces)

    o.pn('<add id="__rm_class_list">')
    o.pn('<name>Classes</name>')
    o.pn('')
    for c in class_list:
        o.pn('   <section pagebreak="true" numbering="false" id='
           + o.q(classId(c.name)) + '/>')
    sorry_nothing_in_this_chapter(class_list, 'classes')
    o.pn('')
    o.pn('</add>')

    # components
    for c in component_list:
        c.printLong(o, doc, no_extern_link = no_extern_link,
                    iface_links = include_interfaces)
        c.printAttributes(o, doc, class_attr = True,
                          no_extern_link = no_extern_link)
        c.printAttributes(o, doc, class_attr = False,
                          no_extern_link = no_extern_link)
        c.printCommands(o, doc, no_extern_link = no_extern_link,
                        iface_links = include_interfaces)

    o.pn('<add id="__rm_component_list">')
    o.pn('<name>Components</name>')
    o.pn('')
    for c in component_list:
        o.pn('   <section pagebreak="true" numbering="false" id='
           + o.q(classId(c.name)) + '/>')
    sorry_nothing_in_this_chapter(component_list, 'components')
    o.pn('')
    o.pn('</add>')

    # interfaces

    if include_interfaces:
        # TODO: maybe we should also list interfaces referenced by this
        # package, but defined by other packages (Simics-Base being a very
        # common special case)
        ifcs = sorted([i for i in ifc_list.values() if i.description],
                      key=sort_key_item)
        for i in ifcs:
            i.printLong(o, doc, no_extern_link = no_extern_link)

        undocumented_ifcs = sorted(i for i in ifc_list.values()
                                   if not i.description)
        if undocumented_ifcs:
            o.pn('<add id="__rm_interfaces_undocumented">')
            o.pn('<name>Undocumented interfaces</name>')
            defined_here = [i for i in undocumented_ifcs
                            if i.defined_here]
            defined_elsewhere = [i for i in undocumented_ifcs
                                 if not i.defined_here]
            if defined_here:
                for i in defined_here:
                    o.pn('<ntarget label="%s"/>' % (ifcId(i.name),))
                o.pn('The following interfaces are defined by this package,'
                     + ' but lack documentation:')
                o.pn(', '.join('<iface>%s</iface>' % (i.name,)
                               for i in defined_here))
                o.pn('<br/>')
            if defined_elsewhere:
                for i in defined_elsewhere:
                    o.pn('<ntarget label="%s"/>' % (ifcId(i.name),))
                o.pn('The following interfaces are used by this package, but'
                     ' defined by other packages:<br/>')
                o.pn(', '.join('<iface>%s</iface>' % (i.name,)
                               for i in defined_elsewhere))
            o.pn('</add>')

        o.pn('<add id="__rm_interface_list">')
        o.pn('<name>Interfaces</name>')
        if ifcs or undocumented_ifcs:
            o.pn('<insert id="rm-interfaces-intro"/>')
            o.pn('')
            if undocumented_ifcs:
                o.pn('   <section pagebreak="true" numbering="false"'
                     + ' id="__rm_interfaces_undocumented"/>')
            for i in ifcs:
                o.pn('   <section pagebreak="true" numbering="false" id='
                     + o.q(ifcId(i.name)) + '/>')
        sorry_nothing_in_this_chapter(ifcs + undocumented_ifcs, 'interfaces')
        o.pn('')
        o.pn('</add>')

    # haps
    if include_haps:
        haps = sorted({hap_list[hap]
                       for m in module_dict.values()
                       for hap in m.haps},
                      key=sort_key_item)
        for h in haps:
            h.printLong(o, doc, no_extern_link = no_extern_link, online = 0,
                        include_modules = include_modules)

        o.pn('<add id="__rm_hap_list" label="haps-chapter">')
        o.pn('<name>Haps</name>')
        o.pn('')
        for h in haps:
            o.pn(
                '   <section numbering="false" id=' + o.q(hapId(h.name)) + '/>')
        sorry_nothing_in_this_chapter(haps, 'haps')
        o.pn('')
        o.pn('</add>')

    o.pn('')
    o.pn('*/')
    o.of.close()

def DOC_print_reference_manual(
        filename, doc, no_extern_link = 0, modules_with_source = [],
        include_commands = True, include_haps = True,
        include_modules = True, include_interfaces = True):
    try:
        print_reference_manual(filename, doc, include_commands, include_haps,
                               include_modules,
                               no_extern_link = no_extern_link,
                               modules_with_source = modules_with_source,
                               include_interfaces = include_interfaces)
        return 1
    except:
        traceback.print_exc()
        try:
            os.remove(filename)
            return 1
        except:
            print("Failed to remove", filename)
            return 0

def print_component_info(filename, doc, no_extern_link = 0):
    o = JdocuOutputHandler(filename)

    class_list = doc.classes

    o.pn('/*')
    o.pn('')

    # classes
    classes = sorted(class_list.values(), key=sort_key_item)
    for c in classes:
        if not 'component' in c.ifc_list:
            continue
        c.printComponent(o, doc, no_extern_link = no_extern_link)
        c.printCommands(o, doc, no_extern_link = no_extern_link)

    # global commands
    module_dict = doc.modules
    gcmd = []
    for m in module_dict:
        gcmd = gcmd + list(module_dict[m].commands.values())

    for g in sorted(gcmd, key = lambda x: x.name):
        g.printComponentCommand(o, doc, '__rm_gcmd_' + labelEncode(g.name),
                                no_extern_link = no_extern_link)

    o.pn('')
    o.pn('*/')
    o.of.close()

def DOC_print_component_info(filename, doc, no_extern_link = 0):
    try:
        print_component_info(filename, doc,
                             no_extern_link = no_extern_link)
        return 1
    except:
        traceback.print_exc()
        try:
            os.remove(filename)
            return 1
        except:
            print("Failed to remove", filename)
            return 0


def get_all_command_categories(cmds):
    '''Gather a set of categories for on-line viewing (filters out
    deprecated commands)'''
    category_set = set()
    for c in cmds:
        if c.is_deprecated():
            continue
        if isinstance(c.type, list):
            category_set.update(set(c.type))
    return category_set

def nc_startswith(a,b):
    return a.lower().startswith(b.lower())

def nc_equal(a,b):
    return a.lower() == b.lower()

def nc_list(l):
    return [x.lower() for x in l]

def nc_in(i,l):
    return (i.lower() in nc_list(l))

def nc_find(i, l):
    for x in l:
        if nc_equal(i, x):
            return x
    return None

complete_parser_filter = {'object', 'class', 'command', 'attribute',
                          'interface', 'hap', 'category', 'script', 'target',
                          'notifier'}

help_parser_filter = complete_parser_filter | {'api', 'module'}

def help_parser(strg, doc, complete = False):
    """Parse help (or tab completion) request for the strg string.

    Arguments:
    strg -- string, topic to search for
    doc -- data structure obtained from DOC_gather_documentation
    complete -- Boolean value, true if requested to generate tab completions

    The following is what is supported for the strg string:
    * commands:
       cmd
       object.cmd
       class.cmd
       interface.cmd
       <class>.cmd
       <interface>.cmd
    * class:
       class
       <class>
       <class>.port_object
    * interface
       interface
       <interface>
    * attribute:
       class(.|->)attribute
       <class>(.|->)attribute
       object(.|->)attribute
    * module
    * hap
    * notifier
    * api (functions and types)

    Return value:
    complete = False: a list of tuples is returned. The first item in
    each tuple identifies which category the help item belongs
    (e.g. 'class', 'interface', 'attribute' etc). All following items
    uniquely identify item in the category (the format differs depending
    on the item category).
    complete = True: a list of tab completed strings is returned.
    """

    import api_help
    import api_doc

    def topics():
        return (t for source in [api_doc.topics, api_help.topics]
                for t in source())

    debug = False
    debug_log = print if debug else lambda *x: None
    debug_log()
    debug_log("calling help_parser(strg = {}, complete = {})".format(
        strg, complete))

    orig_filter = ""                    # filter in query

    is_item_partial_namespace = False   # True if strg matches '<.*' regexp
    is_item_complete_namespace = False  # True if strg matches '<.*>' regexp
    is_namespace_with_brackets = False  # True if strg matches '<.*>.+' regexp

    # does the list of completion contains a potential namespace?
    completion_contains_namespace = False
    completion_contains_filter = False

    # default filter set
    filters = complete_parser_filter if complete else help_parser_filter

    # look for user specified filter
    if ':' in strg:
        (pre_colon, _, rest) = strg.partition(":")
        if pre_colon.lower() in help_parser_filter:
            (orig_filter, strg) = (pre_colon, rest)
            filters = {orig_filter.lower()}
        else:
            if not complete:
                print("Wrong specifier ('{}'), valid specifiers: {}".format(
                    pre_colon, ", ".join(sorted(help_parser_filter))))
            filters = set()

    if strg.startswith("<") and strg not in ('<<', '<', '<='):
        # handle <class>, <class>.attribute, <class>.port, <iface>, <class>.cmd
        namespace = orig_namespace = ""
        if strg.find('>') == len(strg) - 1:
            is_item_partial_namespace = True
            is_item_complete_namespace = True
            item = strg[1:-1]
        elif '>' not in strg:
            is_item_partial_namespace = True
            item = strg[1:]
        else:
            is_namespace_with_brackets = True
            (first, _, rest) = strg.partition(">")
            orig_namespace = first + '>'
            namespace = orig_namespace[1:-1]
            if rest.startswith('->'):
                namespace_marker = '->'
                item = rest[2:]
            elif rest.startswith("."):
                namespace_marker = '.'
                item = rest[1:]
            else:
                # invalid namespace marker
                return []
    else:
        # split into namespace/item
        _arrow = strg.rfind('->')
        _dot = strg.rfind('.')
        if _arrow > 0:
            # only attributes can be documented this way
            filters = filters & {'attribute'}
            namespace_marker = '->' # replace the namespace marker
            orig_namespace = strg[0:_arrow]
            item = strg[_arrow + 2:]
        elif _dot > 0:
            namespace_marker = "."
            orig_namespace = strg[0:_dot]
            item = strg[_dot + 1:]
        else:
            # default namespace marker that works for every case
            namespace_marker = "."
            orig_namespace = ""
            item = strg
        namespace = orig_namespace

    # look at the potential namespaces we will be looking at
    potential_namespaces = set()
    if namespace:
        if not is_namespace_with_brackets:
            o = None
            try:
                o = get_object(namespace)
            except simics.SimExc_General:
                pass
            if o is None and '.' in namespace:
                try:
                    SIM_get_class(namespace)
                    potential_namespaces.add((namespace, "class"))
                except:
                    (_ns, _, _rest) = namespace.partition(".")
                    try:
                        o = get_object(_ns)
                    except simics.SimExc_General:
                        pass
                    orig_namespace = orig_namespace.partition(".")[0]
                    namespace = _ns
                    item = _rest + "." + item
            if o is not None:
                potential_namespaces.add((o.classname, "class"))
                for i in o.attr.iface:
                    potential_namespaces.add((i, "ifc"))

        for o in simics.SIM_object_iterator(None):
            for i in o.attr.iface:
                if nc_equal(namespace, i):
                    potential_namespaces.add((i, "ifc"))
        for c in SIM_get_all_classes():
            if nc_equal(namespace, c):
                potential_namespaces.add((c, "class"))
        # Consider interfaces of loaded classes only, to avoid loading modules.
        if doc:
            for c in doc.classes.values():
                for i in c.ifc_list:
                    if nc_equal(namespace, i):
                        potential_namespaces.add((i, "ifc"))

        api_ns = set()
        for m in topics():
            p = m.rfind('.')
            if p >= 0:
                api_ns.add(m[:p])

        for m in api_ns:
            if nc_equal(namespace, m):
                potential_namespaces.add((m, "api"))

        if not potential_namespaces:
            # we have an unknown namespace... never matches!
            return []

    debug_log("potential_namespaces", potential_namespaces)

    # results
    results = []                        # exact results (for parsing)
    tab_results = []                    # tab-completion results

    # look for matching filters
    if complete and len(filters) > 1 and not namespace:
        for f in help_parser_filter:
            if nc_startswith(f, item):
                tab_results.append(f + ":")
                completion_contains_filter = True

    cmds = simics_commands()

    # tab-complete on categories
    if nc_in('category', filters) and not namespace:
        for c in get_all_command_categories(cmds):
            if nc_equal(c, item):
                results.append(("category", c))
            if complete and nc_startswith(c, item):
                tab_results.append(c)

    # look for class.port combination, e.g. <class>.port
    if 'class' in filters and namespace and namespace_marker == '.':
        for (c, t) in potential_namespaces:
            if t != 'class':
                continue
            _ports = VT_get_port_classes(c)
            for p in _ports:
                if p == item:
                    results.append(('class', _ports[p]))
                if complete and p.startswith(item):
                    tab_results.append(orig_namespace + '.' + p)
                    completion_contains_namespace = True

    # look for object descendants
    if ('object' in filters and namespace and namespace_marker == "."
        and not is_namespace_with_brackets):
        try:
            obj = get_object(namespace)
        except simics.SimExc_General:
            pass
        else:
            slots = {o.name[o.name.rfind("."):]: o
                     for o in simics.CORE_shallow_object_iterator(obj, True)}
            for member in slots:
                if member == namespace_marker + item:
                    _cls = slots[member].classname
                    results.append(('class', _cls))
                    tab_results.append(orig_namespace + member + '.')
                if complete and member.startswith(namespace_marker + item):
                    tab_results.append(orig_namespace + member)
                    completion_contains_namespace = True

    # look in command only if we are not tab-completing a namespace
    if (nc_in('command', filters) and not is_item_partial_namespace
        and namespace_marker == '.'):
        potential_cmds = []
        if potential_namespaces:
            for (n,t) in potential_namespaces:
                potential_cmds.append('<' + n + '>.' + item)
        else:
            potential_cmds.append(item)

        for c in cmds:
            # avoid completing on namespace commands without namespace
            cmd_namespace = c.cls or c.iface
            if cmd_namespace and not namespace:
                continue
            if not cmd_namespace and namespace:
                continue
            # gather command name + aliases
            cnames = [c.name]
            for a in c.alias:
                if cmd_namespace:
                    cnames.append('<' + cmd_namespace + ">." + a)
                else:
                    cnames.append(a)
            for cname in cnames:
                for pc in potential_cmds:
                    if not pc:
                        continue
                    if nc_equal(cname, pc):
                        results.append(('command', cname))
                    if complete and nc_startswith(cname, pc):
                        if orig_namespace:
                            tab_results.append(
                                orig_namespace + namespace_marker
                                + stripCommandName(cname))
                        else:
                            tab_results.append(cname)

    debug_log("tab_results after commands", tab_results)

    # look for object aliases only if we are not tab-completing a namespace, as
    # part of commands
    if (nc_in('command', filters) and not is_item_partial_namespace
        and not namespace):
        tab_results += obj_aliases().completions(item, True)
        if item in tab_results:
            results.append(('command', item))

    debug_log("tab_results after built-in object aliases", tab_results)

    # look for matching object, only if not tab-completing a namespace
    if (not potential_namespaces
        and not is_item_partial_namespace
        and (nc_in('object', filters)
             or (not namespace and complete
                 and (nc_in('attribute', filters)
                      or nc_in('command', filters))))):
        for (s,o) in visible_objects().items():
            if nc_equal(item, s):
                results.append(('class', o.classname))
            if complete and nc_startswith(s, item):
                if nc_in('object', filters):
                    tab_results.append(s)
                    completion_contains_namespace = True
                if (nc_in('command', filters)
                    or nc_in('attribute', filters)):
                    tab_results.append(s + '.')
                    completion_contains_namespace = True

    debug_log("tab_results after objects", tab_results)

    # look for matching class (the parent_class.portname case is handled below)
    if (not potential_namespaces
        and (nc_in('class', filters)
             or (not namespace and complete
                 and (nc_in('attribute', filters)
                      or nc_in('command', filters))))):
        all_loaded_classes = set(SIM_get_all_classes())
        all_classes = all_loaded_classes.union(
            simics.CORE_get_all_known_module_classes())
        for c in sorted(all_classes):
            if nc_equal(c, item):
                if not ("class", c) in results:
                    results.append(('class', c))
            # don't count a match if item is complete namespace
            if (complete
                and nc_startswith(c, item)
                and not is_item_complete_namespace):
                if nc_in('class', filters):
                    completion_contains_namespace = True
                    tab_results.append('<' + c + '>'
                                       if is_item_partial_namespace else c)
                if (c in all_loaded_classes
                    and (nc_in('command', filters)
                         or nc_in('attribute', filters))):
                    completion_contains_namespace = True
                    tab_results.append('<' + c + '>.'
                                       if is_item_partial_namespace
                                       else c + '.')

    # look for matching "parent_class.portname" classes
    if (nc_in('class', filters)
        and any(t == 'class' for (_, t) in potential_namespaces)
        and namespace_marker == '.'
        and not is_namespace_with_brackets):
        classname = namespace + "." + item
        for c in SIM_get_all_classes():
            if c == classname:
                results.append(("class", classname))
            if complete and c.startswith(classname):
                completion_contains_namespace = True
                tab_results.append('<' + c + '>'
                                   if is_item_partial_namespace else c)
                if(nc_in('command', filters)
                   or nc_in('attribute', filters)):
                    tab_results.append('<' + c + '>.'
                                       if is_item_partial_namespace
                                       else c + '.')


    debug_log("tab_results after classes", tab_results)

    # look for matching interface
    if (not potential_namespaces
        and (nc_in('interface', filters)
             or (not namespace and complete and (nc_in('command', filters))))):
        iface_list = {}
        for o in simics.SIM_object_iterator(None):
            for i in o.attr.iface:
                iface_list[i] = 1

        for i in iface_list:
            if nc_equal(item, i):
                results.append(("interface", i))
            if (complete
                and nc_startswith(i, item)
                and not is_item_complete_namespace):
                completion_contains_namespace = True
                tab_results.append('<' + i + '>' if is_item_partial_namespace
                                   else i)

    debug_log("tab_results after interfaces", tab_results)

    # look for matching attributes
    if potential_namespaces and nc_in('attribute', filters):
        potential_classes = []
        for (n,t) in potential_namespaces:
            if t == "class":
                potential_classes.append(n)
        for c in potential_classes:
            attrdesc = simics.VT_get_all_attributes(c)
            for i in attrdesc:
                name = i[0]
                internal = ((i[2] & Sim_Attr_Internal) != 0)
                if nc_equal(item, name):
                    results.append(('attribute', (c, name, internal)))
                if complete and nc_startswith(name, item) and not internal:
                    tab_results.append(orig_namespace + namespace_marker + name)

    debug_log("tab_results after attributes", tab_results)

    # look for matching module
    if (not potential_namespaces
        and not is_item_partial_namespace
        and nc_in('module', filters)):

        for (module_name, _, is_loaded, *_) in SIM_get_all_modules():
            if is_loaded:
                if nc_equal(item, module_name):
                    results.append(('module', module_name))
                if complete and nc_startswith(module_name, item):
                    tab_results.append(module_name)

    debug_log("tab_results after modules", tab_results)

    # look for matching hap
    if (not potential_namespaces
        and not is_item_partial_namespace
        and nc_in('hap', filters)):
        for (name, *_) in conf.sim.hap_list:
            if nc_equal(name, item):
                results.append(('hap', name))
            if complete and nc_startswith(name, item):
                tab_results.append(name)

    debug_log("tab_results after haps", tab_results)

    # look for matching notifiers
    if (not potential_namespaces
        and not is_item_partial_namespace
        and nc_in('notifier', filters)):
        for (name, *_) in conf.sim.notifier_list:
            if nc_equal(name, item):
                results.append(('notifier', name))
            if complete and nc_startswith(name, item):
                tab_results.append(name)

    debug_log("tab_results after notifiers", tab_results)

    # look for matching api information
    if nc_in('api', filters):
        prefixes = set()
        for n, t in potential_namespaces:
            if t == 'api':
                prefixes.add(n + '.')
        if not prefixes:
            prefixes.add('')
        for prefix in prefixes:
            key = nc_find(prefix + item, topics())
            if key:
                results.append(('api', key))
        if complete:
            for k in topics():
                if any(nc_startswith(k, prefix + item)
                       for prefix in prefixes):
                    tab_results.append(k)

    debug_log("tab_results after api", tab_results)

    if complete:
        # work-around so that we don't have only one completion if we are
        # still completing on a namespace or a filter
        if len(tab_results) == 1:
            # namespace
            if (completion_contains_namespace and
                (nc_in('command', filters) or nc_in('attribute', filters))):
                if orig_filter:
                    new_completions = help_parser(orig_filter + ":"
                                                  + tab_results[0]
                                                  + '.', doc, True)
                else:
                    new_completions = help_parser(tab_results[0]
                                                  + '.', doc, True)
                if new_completions:
                    if len(filters) == 1:
                        # no need to complete with the filter, it's already
                        # done by the recursive call to the parser
                        return new_completions
                    else:
                        tab_results = [tab_results[0],
                                       tab_results[0] + '.']
            elif completion_contains_filter:
                new_completions = help_parser(tab_results[0], doc, True)
                return new_completions

        debug_log("tab_results after adding '.' or '->'", tab_results)
        if len(filters) == 1 and orig_filter:
            tresults = []
            for t in tab_results:
                # check if the result is quoted first
                if t and len(t) > 1 and t[0] == '"' and t[-1] == '"':
                    tresults.append('"' + orig_filter + ":" + t[1:])
                else:
                    tresults.append(orig_filter + ":" + t)
        else:
            tresults = tab_results
        debug_log("final tab_results", tresults)
        return tresults
    else:
        return results

topic_priority = ['command', 'category', 'class', 'interface', 'hap',
                  'notifier', 'module', 'attribute', 'api']

def help_select_topic(match):
    # select the most appropriate in order of priority
    real_match = []
    other_match = []
    for cat in topic_priority:
        for (t,n) in match:
            if t == cat:
                real_match = [(t,n)]
            else:
                other_match.append((t,n))
        if real_match:
            return (real_match, other_match)
        else:
            other_match = []
    # should never come here, there wouldn't be any real_match?
    raise Exception("Error: Several topics were found but none of them can"
                    " be selected")

help_printers = {}
def help_printer(topic):
    '''Decorator to add function as handler for a help topic'''
    def add_to_dict(f):
        help_printers[topic] = f
        return f
    return add_to_dict

_api_help_comments = {
    'obj_hap_func_t': ('// See documentation on the specific hap type to see what\n'
                       '// the appropriate function signature should be.'),
}

@help_printer('api')
def print_api_help(topic, ignore = None, n = None):
    import api_help
    from api_doc import print_doc
    import commands

    if print_doc(topic):
        return

    api_doc = commands.get_api_help_description()

    if topic in api_doc:
        # Print the long description first and continue with the short
        format_print(api_doc[topic])
        format_print('\n\n<b>SHORT DESCRIPTION</b>\n\n')

    if n:
        format_print('<i>API <b>%s</b></i>\n\n' % (n,))

    topic_help = api_help.api_help(topic)
    if len(topic_help) == 2:
        format_print(topic_help[0])
        return

    default_api = default_api_version()

    filename, include_filename, groups, typestr = topic_help
    if filename is not include_filename:
        print('// defined in simics/%s' % filename)
    if include_filename == 'device-api.h':
        print('#include <simics/%s>      // in C/C++' % include_filename)
    else:
        print('#include <simics/%s>      // in C' % include_filename)
        if api_help.api_cxx_available(topic):
            print('#include <simics/c++/%s>  // in C++' % include_filename)
        else:
            print('// not available in C++')
    if not api_help.api_dml_available(topic):
        print('// not available in DML')
    elif include_filename != 'device-api.h':
        assert include_filename.endswith('.h')
        print('import "simics/%s.dml";     // in DML' % include_filename[:-2])
    else:
        print('// always available in DML')
    print()

    ngroups = 0
    has_unsupported = False
    for apis, help in groups:
        ngroups += 1
        if help is None:
            has_unsupported = True

    if ngroups == 2 and has_unsupported:
        indent = ''
    elif ngroups > 1:
        indent = '    '
    else:
        indent = ''

    for apis, help in reversed(groups):
        old_event_api = False
        if '4.0-old-event' in apis:
            # either remove this API, or assert it's the only one
            # in this group
            if '4.0' in apis:
                apis = set(apis)
            else:
                old_event_api = True
            apis = list(apis)
            apis.remove('4.0-old-event')

        if indent:
            print('-' * 79)

        if help:
            if default_api not in apis:
                if ngroups == 2 and has_unsupported:
                    prefix = 'only supported '
                else:
                    prefix = ''

                if latest_api_version() in apis:
                    apis += ('latest',)

                if apis:
                    print('%s// %swith SIMICS_API = %s' % (
                        indent, prefix, ' / '.join(sorted(apis))))
                if old_event_api:
                    if apis:
                        prefix = 'or '
                    else:
                        prefix = ''
                    print(('%s// %swith SIMICS_API = 4.0 and'
                           ' -DALLOW_OLD_EVENT_API') % (
                        indent, prefix))

            comment = _api_help_comments.get(topic, None)
            if comment is not None:
                help = '%s\n%s' % (help, comment)

            if indent:
                help = '\n'.join(indent + l for l in help.split('\n'))
            print_wrap_code(help, terminal_width() - 1)
        elif set(apis) == set([latest_api_version]):
            print(('%s// This API has been deprecated in'
                   ' the latest version of Simics.') % (indent,))
            print(('%s// It is not available with'
                   ' SIMICS_API = %s / latest') % (
                indent, latest_api_version))
    print()

    def in_python(sym):
        return hasattr(simics, sym)

    if typestr[0] in 'su':
        parts = typestr.split(':')
        name = parts[1]
        if not (name and in_python(name)):
            print('// not available in Python')
            return
        the_class = getattr(simics, name)

        try:
            # try to instantiate; will not work for some types
            obj = the_class()
        except TypeError as msg:
            if 'cannot create' in str(msg):
                print('// cannot be instantiated from Python')
                return
            if ('Required argument' in str(msg)
                or 'required argument' in str(msg)):
                # The Python constructor requires arguments, but we don't
                # know more than that right now.
                print('// available in Python')
                return
            raise

        # struct members available in Python
        members_in_py = set(m for m in dir(obj) if not m.startswith('__'))
        # struct members available in C
        if len(parts) >= 3:
            members_in_c = set(parts[2].split(';'))
        else:
            members_in_c = set()
        # struct members available in C, but no in Python
        not_in_py = members_in_c - members_in_py

        if not not_in_py:
            print('// available in Python')
            return
        if not members_in_py:
            print('// no fields available in Python')
            return

        def fields_are(l):
            l = sorted(l)
            if len(l) == 1:
                return 'field %s is' % (l[0],)
            return 'fields %s are' % (concat_comma(l, word = "and"),)

        # use the way of saying this which is shorter
        if sum(map(len, not_in_py)) <= sum(map(len, members_in_py)):
            line = '// %s not available in Python' % (
                fields_are(not_in_py),)
        else:
            line = '// only %s available in Python' % (
                fields_are(members_in_py),)
        print_wrap_code(line, terminal_width() - 1,
                        continuation_indent = '// ')
        return
    elif typestr.startswith('e:'):
        _, _, members_in_c = typestr.split(':')
        members_in_py = list(map(in_python, members_in_c.split(';')))
        all_py = all(members_in_py)
        any_py = any(members_in_py)
        print('// %s available in Python' % (
            'members' if all_py else 'some members' if any_py else 'not',))
        return
    elif typestr in 'ft':
        print('// %savailable in Python' % (
            '' if in_python(topic) else 'not ',))
        return

    # t40_commands/s-api-help verifies that we never get here
    assert False

@help_printer('class')
def print_class_help(n, doc, o):
    cl = doc.classes.get(n)
    if not cl:
        # try class aliases
        for alias, cls in simics.CORE_get_all_class_aliases():
            if n == alias:
                cl = doc.classes.get(cls)
                if cl:
                    break
    if cl:
        cl.printLong(o, doc, online = 1)
        cl.printCommands(o, doc)
    else:
        cl = ClassNotLoadedDesc(n)
        cl.printLong(o, online = 1)
    o.pn('')

@help_printer('command')
def print_command_help(n, doc, o):
    try:
        cmd = doc.commands[n]
    except:
        cmd = doc.command_aliases[n]
    cmd.printLong(o, doc, online = 1)

@help_printer('attribute')
def print_attribute_help(n, doc, o):
    (cl_name, attr_name, internal) = n
    cl = doc.classes[cl_name]
    cl.printSingleAttribute(o, doc, attr_name, online = 1)

@help_printer('module')
def print_module_help(n, doc, o):
    md = doc.modules[n]
    md.printLong(o, doc, online = 1)

@help_printer('hap')
def print_hap_help(n, doc, o):
    hp = doc.haps[n]
    hp.printLong(o, doc, online = 1)

@help_printer('notifier')
def print_notifier_help(n, doc, o):
    hp = doc.notifiers[n]
    hp.printLong(o, doc, online = 1)

@help_printer('category')
def print_category_help(n, doc, o):
    gcmds = sorted(doc.command_categories[n])

    # Find how many characters the command name column should
    # have. Ignores command names that have really long names;
    # these will force a line-break after the name.
    def cmd_len_reduce(width, cmd):
        l = len(cmd.name)
        if l > terminal_width() / 2:
            return width
        else:
            return max(width, l)
    max_len = reduce(cmd_len_reduce, gcmds, 0)

    o.pn('<b>Commands available in the "%s" category:</b><br>' % n)
    for gc in gcmds:
        markup_name = '<cmd>%s</cmd>' % o.encode(gc.name)
        if len(gc.name) > max_len:
            o.pn(markup_name)
        else:
            o.pr(markup_name + '&nbsp;' * (max_len - len(gc.name) + 3))

        o.pr(gc.short)
        o.pr('<br>\n')
    o.pn('')

@help_printer('interface')
def print_interface_help(n, doc, o):
    ifc = doc.ifaces[n]
    ifc.printLong(o, doc, online = 1)

def print_other_match_info(other_match):
    other_list = []
    for (t, n) in other_match:
        if t == 'attribute':
            (aclass, aname, internal) = n
            if not internal:
                other_list.append(t + ':' + aclass + '.' + aname)
        else:
            other_list.append(t + ":" + n)
    if len(other_list) > 0:
        format_print("<b>Note</b> that your request also matched"
                     " other topics:<br/>")
        for item in other_list:
            print("  " + item)
        print()

assert set(topic_priority) == set(help_printers)

def print_help(doc, real_match):
    o = TerminalOutputHandler()
    (t,n) = real_match[0]
    help_fun = help_printers.get(t)
    assert help_fun # Make sure we have a handler for type t
    help_fun(n, doc, o)
    o.flush()

def print_help_help():
    format_print(
        "The <cmd>help</cmd> command shows information on any topic, like"
        " a command, a class, an object, an interface, a hap, a module, an"
        " attribute or a function or type from the Simics API.\n\n")
    format_print(
        "To get more information about the help command,"
        " type <cmd>help help</cmd>.\n\n")
    format_print(
        "Type <cmd>help <arg>category</arg></cmd> to list the commands for"
        " a specific category. Here is a list of command categories:\n\n")
    cat_list = sorted(get_all_command_categories(simics_commands()))
    print_columns('l', [ "  " + x for x in cat_list],
                  has_title = 0, wrap_space = "")
    print()
    format_print(
        "The complete documentation may also be read in a web browser by"
        " running the <file>documentation</file> script found in the Simics"
        " project folder.\n\n")

def help_cmd(strg):
    if not strg: # help without argument
        print_help_help()
        return

    try:
        doc = DOC_gather_documentation(online = True, include_deprecated = False)
    except DocException as msg:
        raise CliError("Failed to gather documentation: %s" % msg)

    match = help_parser(strg, doc)

    if strg in user_defined_aliases():
        print(("'" + strg + "' is a user defined alias for '"
               + user_defined_aliases()[strg] + "'"))
        if not match:
            return

    obj_alias = obj_aliases().get_alias(strg)
    if obj_alias:
        print(f"'{strg}' is an alias for {obj_alias.description}")
        return

    if not match:
        idx = strg.find(':')
        specifier = strg[:idx]
        maybe_target = strg[idx + 1:]
        if specifier == 'target':
            import command_file
            from targets import script_params
            try:
                command_file.print_params_for_target(maybe_target)
                return
            except script_params.TargetParamError as ex:
                raise CliError(ex)
            except simics.SimExc_General as ex:
                raise CliError(ex)

    # If there are no other matches, then check if help string is a script file
    # with a script declaration block. This code should probably be merged with
    # the help parser above, with tab-completion added (if script: used).
    if not match:
        maybe_file = strg[strg.find(':') + 1:]
        if os.path.isfile(maybe_file):
            import command_file
            if command_file.print_help_for_script(maybe_file, header = False):
                return

    if not match:
        raise CliError(f"No help topic matching '{strg}'."
                       " Try using the help-search and api-search commands.")

    # if several matches, select the one with highest priority
    (real_match, other_match) = help_select_topic(match)
    print_help(doc, real_match)

    if other_match:
        print_other_match_info(other_match)

def is_likely_script_with_params(filename):
    (_, filename) = expand_path_markers(filename)
    try:
        f = open(filename)
    except OSError:
        return False
    with f:
        try:
            for x in f:
                x = x.strip()
                if not x or x.startswith("#"):
                    continue
                return x.startswith("decl {")
        except UnicodeDecodeError:  # possible if we opened a binary file
            return False
        return False

# script files with a script parameter declaration block
def script_file_expander(comp):
    prefix = "script:" if comp.startswith("script:") else ""
    return [(prefix + x, os.path.isdir(x))
            for x in file_expander(comp[len(prefix):])
            if os.path.isdir(x) or is_likely_script_with_params(x)]

def help_exp(comp):
    try:
        c = help_parser(comp, None, complete = True)
    except:
        traceback.print_exc(file = sys.stdout)
        return []
    if not c:
        if comp.startswith('target:'):
            from targets.sim_params import target_expander
            idx = comp.find(':')
            maybe_target = comp[idx + 1:]
            return ['target:' + t for t in target_expander(maybe_target)]

        # Mixing file name expanders with other expanders does not work well
        # (different format). Only use script file expander if no other match.
        c = script_file_expander(comp)
    return c

new_command("help", help_cmd, [arg(str_t, "topic", "?", expander = help_exp)],
            short = "help command",
            alias=["h", "man"],
            type = ["Help"],
            see_also = ["help-search", "api-help", "api-search"],
            doc = f"""
Prints help information on <arg>topic</arg>. <arg>topic</arg> can be a
command, a class, an object, an interface, a module, a hap, an
attribute or a function or type from the Simics API. Here are some
usage examples of the <cmd>help</cmd> command:

<pre>
simics> <b>help print-time</b>
[... print-time command documentation ...]

simics> <b>help cpu0.disassemble</b>
[... &lt;processor&gt;.disassemble command documentation ...]

simics> <b>help &lt;processor&gt;.disassemble</b>
[... &lt;processor&gt;.disassemble command documentation ...]

simics> <b>help cpu0.core[0][0]</b>
[... &lt;x86QSP1&gt; class documentation ...]

simics> <b>help x86QSP1</b>
[... &lt;x86QSP1&gt; class documentation ...]

simics> <b>help processor</b>
[... &lt;processor&gt; interface documentation ...]

simics> <b>help x86QSP1.freq_mhz</b>
[... &lt;x86QSP1&gt;.freq_mhz attribute documentation ...]

simics> <b>help x86QSP1.msr_aperf</b>
[... &lt;x86QSP1&gt;.msr_aperf attribute documentation ...]

simics> <b>help Core_Exception</b>
[... Core_Exception hap documentation ...]

simics> <b>help SIM_get_mem_op_type</b>
[... SIM_get_mem_op_type() function declaration ...]

simics> <b>help script.simics</b>
[... script parameter information from the script file script.simics ...]
</pre>

To refine your search and improve the tab-completion choices, you may use
filters in the topic as shown below:

   <cmd>help</cmd> topic = command:break

The recognized filters are
{", ".join('"{}:"'.format(f) for f in sorted(help_parser_filter))}.

By default, the help command does not provided tab-completion on
<arg>topic</arg> for modules and api symbols unless the specific filter is
provided.
""")

_tagfilter = re.compile("</?(tt|i|b|em|br/?)>")

def _regexp_find(text, pattern):
    return pattern.search(_tagfilter.sub("", text))

def _substring_find(text, pattern):
    return pattern in _tagfilter.sub("", text.lower())

def apropos_cmd(text, regexp = 0, search_attrs = False):
    try:
        doc = DOC_gather_documentation(online = 1)
    except DocException as msg:
        raise CliError("Failed to gather documentation: %s" % msg)

    if regexp:
        finder = _regexp_find
        try:
            pattern = re.compile(text, re.IGNORECASE)
        except Exception as msg:
            raise CliError("Invalid regular expression '%s': %s" % (text, msg))
        desc = "Text matching the regular expression"
    else:
        finder = _substring_find
        pattern = text.lower()
        desc = "The text"

    # look in commands
    def search_cmd_see_also(sc, pattern):
        if sc.see_also:
            for s in sc.see_also:
                if finder(s, pattern):
                    return 1
        return 0

    cmd_found = []
    for c in doc.commands.values():
        sc = c.cmd
        if (finder(sc.doc, pattern)
            or finder(sc.name, pattern)
            or finder(sc.short, pattern)
            or finder(sc.group_short, pattern)
            or search_cmd_see_also(sc, pattern)):
            cmd_found.append(('command', c.name))
        elif isinstance("", type(sc.alias)):
            if finder(sc.alias, pattern):
                cmd_found.append(('command', c.name))
        else:
            for a in sc.alias:
                if finder(a, pattern):
                    cmd_found.append(('command', c.name))
                    break
    cmd_found.sort()

    # look in class documentation
    class_found = []
    attr_found = []
    for c in doc.classes.values():
        if (finder(c.name, pattern)
            or finder(c.description, pattern)):
            class_found.append(('class', c.name))
        if search_attrs:
            for a in c.attr_info.values():
                if (finder(a.name, pattern)
                    or finder(a.description, pattern)):
                    attr_found.append(('attribute', '<' + c.name + '>.'
                                       + a.name))
    class_found.sort()
    attr_found.sort()

    # look in interface list
    ifc_found = []
    for i in doc.ifaces.values():
        if (finder(i.name, pattern)):
            ifc_found.append(('interface', i.name))
    ifc_found.sort()

    # look in hap_list
    hap_found = []
    for h in doc.haps.values():
        if (finder(h.name, pattern)
            or finder(h.help, pattern)):
            hap_found.append(('hap', h.name))
    hap_found.sort()

    found = cmd_found + class_found + attr_found + ifc_found + hap_found
    if found:
        print("%s '%s' appears in the documentation" % (desc, text))
        print("for the following items:\n")
        for t,n in found:
            print('%-10s     %s'%(t.capitalize(), n))
        print()
    else:
        raise CliError("%s '%s' cannot be found in any documentation." % (
            desc, text))

new_command("help-search", lambda re, attr, strg: apropos_cmd(strg, re, attr),
            [arg(flag_t, "-r"), arg(flag_t, "-a"), arg(str_t, "string") ],
            short = "search for text in documentation",
            alias = ["a", "apropos", "search"],
            type = ["Help"],
            see_also = ["api-search", "help", "api-help"],
            doc = """
Print all items for which the documentation contains the text
<arg>string</arg>. With the <tt>-r</tt> flag, the <arg>string</arg> is
interpreted as a regular expression.

This command will only display search results for commands, classes,
haps, and interfaces from the common documentation as well as the
currently loaded configuration. With the <tt>-a</tt> flag, attributes
are also searched.""")

class _Helper:
    '''This is a wrapper around pydoc.help.'''
    def __repr__(self):
        return "Type help(object) for help about 'object'."
    def __call__(self, obj = None):
        if obj is None:
            for p in ('This is the online help utility for Python.\n\n',
                      '''At the Simics prompt, type
<cmd>@help(<var>object</var>)</cmd> for help on <arg>object</arg>,
which may be any module, class, or function.\n\n''',
                      '''Documentation on supported Simics-specific
Python API functions can be found using the <cmd>api-help</cmd>
command.\n\n'''):
                format_print(p)
            return

        simicsdoc = getattr(obj, '__simicsdoc__', None)
        if simicsdoc is not None:
            import api_help
            doc = api_help.api_help('%s.%s' % (simicsdoc.module,
                                               simicsdoc.name))
            if doc and len(doc) == 2:
                if inspect.isfunction(obj):
                    typename = 'function'
                elif inspect.ismethod(obj):
                    typename = 'method'
                elif inspect.isclass(obj):
                    typename = 'class'
                else:
                    typename = 'object'
                format_print(
                    'Help on Simics API Python %s <fun>%s.%s</fun>\n\n' % (
                        typename, simicsdoc.module, simicsdoc.name))
                format_print(doc[0])
                return

        return pydoc.help(obj)

builtins.help = _Helper()

def _get_function_synopsis(fun):
    '''Return the function synopsis of 'fun'.'''
    func_code = fun.__code__
    fname = func_code.co_filename
    firstline = func_code.co_firstlineno - 1

    doc_re = re.compile(r'\s*@(cli\.)?doc\(')
    def_re = re.compile(r'\s*def\s')
    end_re = re.compile(r'\):')
    # 0 - looking for first line
    # 1 - skipping doc()
    # 2 - reading def
    mode = 0

    result = ''

    try:
        f = codecs.open(fname, "r", "utf-8")
    except IOError:
        # Return empty synopsis if file of function not found (bug 20512)
        return ''

    for lineno, line in enumerate(f.readlines()):
        if mode == 0:
            if lineno < firstline:
                continue
            if doc_re.match(line):
                mode = 1
                continue
        line = line.expandtabs()
        if mode == 1:
            m = def_re.match(line)
            if not m:
                continue
            def_len = m.end()
            mode = 2

            m = end_re.search(line)
            if m:
                f.close()
                return line[def_len:m.start() + 1]

            result += line[def_len:]
            def_indent = ' ' * def_len
            continue
        if mode == 2:
            if line.startswith(def_indent):
                line = line[def_len:]
            m = end_re.search(line)
            if m:
                f.close()
                return result + line[:m.start() + 1]
            result += line

    f.close()
    raise Exception('cannot find synopsis for %r' % (fun,))

def DOC_print_python_refmanual(ofile, jdocu_mode = False):
    class DocuPrinter:
        @staticmethod
        def print_head(ofile):
            print('/*', file=ofile)
        @staticmethod
        def print_item_start(ofile, namespace, simicsdoc):
            longndx = [ '%s Python module' % (simicsdoc.module,) ]
            if simicsdoc.namespace:
                longndx.append(simicsdoc.namespace)
            longndx.append(simicsdoc.name)
            # TeX only shows 3 index levels; do not use more
            longndx = '.'.join(longndx).replace('.', '!', 2)
            print((
                '<add id="%(doc_id)s">\n'
                '  <name>%(namespace)s.%(name)s%(call)s</name>\n'
                '  <ndx>%(name)s</ndx> <ndx>%(longndx)s</ndx>\n'
                '  <doc>\n') % {
                    'doc_id'    : simicsdoc.doc_id,
                    'namespace' : namespace,
                    'longndx'   : longndx,
                    'name'      : simicsdoc.name,
                    'call'      : '()' if simicsdoc.is_function else ''
                }, file=ofile)
        @staticmethod
        def print_item(ofile, dt, dd, label):
            if label:
                label = ' label="%s"' % (label,)
            else:
                label = ''
            print('    <di name="%s"%s>%s</di>' % (
                dt.upper(), label, dd), file=fout)
        @staticmethod
        def print_item_end(ofile):
            print('  </doc>', file=ofile)
            print('%s</add>' % (simicsdoc.docu_suffix,), file=ofile)
            print(file=ofile)
        @staticmethod
        def print_end(ofile):
            print('*/', file=ofile)

    insert_re = re.compile('^<insert[^>]*>$')
    class PyPrinter:
        @staticmethod
        def print_head(ofile):
            print('api_help_py = {', file=ofile)
        @staticmethod
        def print_item_start(ofile, namespace, simicsdoc):
            print('<dl>', file=ofile)
        @staticmethod
        def print_item(ofile, dt, dd, label):
            if insert_re.match(dd):
                dd = 'See separate manual.'
            print('  <dt><b>%s</b></dt>' % (dt,), file=ofile)
            print('    <dd>%s</dd>' % (dd,), file=ofile)
        @staticmethod
        def print_item_end(ofile):
            print('</dl>', file=ofile)
        @staticmethod
        def print_end(ofile):
            print('}', file=ofile)

    def sort_key(item):
        d = item.__simicsdoc__
        return (d.module, d.namespace, d.name)

    o = DocuPrinter if jdocu_mode else PyPrinter

    escape = cli_impl.html_escape

    if ofile is None:
        ofile = sys.stdout
    elif not isinstance(ofile, io.IOBase):
        ofile = open(ofile, 'w')

    o.print_head(ofile)

    for obj in sorted(cli_impl._simics_doc_items, key=sort_key):
        if jdocu_mode:
            fout = ofile
        else:
            fout = StringIO()

        simicsdoc = obj.__simicsdoc__
        namespace = simicsdoc.module
        if simicsdoc.namespace:
            namespace = '%s.%s' % (namespace, simicsdoc.namespace)

        if simicsdoc.synopsis is None:
            synopsis = escape(_get_function_synopsis(obj))
        else:
            synopsis = simicsdoc.synopsis
        fields = [
            ('Name',
             '<b>%s</b> &mdash; %s' % (simicsdoc.name, simicsdoc.short),
             '%s.%s' % (namespace, simicsdoc.name))]
        if synopsis:
            fields.append(('Synopsis',
                           '<pre%s>%s</pre>' % (
                        ' size="small"' if jdocu_mode else '',
                        synopsis)))

        def fix_space(s):
            '''Expand tabs, remove uniform leading spaces.'''
            class D: __doc__ = s
            return inspect.getdoc(D)

        fields.append(('Description', fix_space(simicsdoc.body)))
        if simicsdoc.return_value:
            fields.append(('Return Value', fix_space(simicsdoc.return_value)))
        if simicsdoc.exceptions:
            fields.append(('Exceptions', fix_space(simicsdoc.exceptions)))
        if simicsdoc.example:
            fields.append(('Example', fix_space(simicsdoc.example)))
        if simicsdoc.see_also:
            fields.append(('See Also', fix_space(simicsdoc.see_also)))
        if simicsdoc.context:
            fields.append(('Execution context', fix_space(simicsdoc.context)))

        o.print_item_start(fout, namespace, simicsdoc)

        for field in fields:
            dt, dd = field[:2]
            label = field[2] if len(field) > 2 else None
            o.print_item(fout, dt, dd, label)

        o.print_item_end(fout)

        if not jdocu_mode:
            def pdoc(s):
                ofile.write("(''")
                for l in s.split('\n'):
                    ofile.write('\n    ')
                    ofile.write(repr(l + '\n'))
                ofile.write(")")

            doc = fout.getvalue().rstrip()
            ofile.write('  %r : ( ' % ('%s.%s' % (
                    namespace, simicsdoc.name)))
            pdoc(doc)
            ofile.write(',\n    ')
            pdoc(get_format_string(doc, mode = 'text', width = 70))
            print(" ),", file=ofile)
            print(file=ofile)

        realobj = __import__(simicsdoc.module)
        for a in (namespace.split('.')[1:] + [ simicsdoc.name]):
            realobj = getattr(realobj, a, None)
            if not realobj:
                break
        if (realobj is not obj
            and type(realobj) is not obj
            and not (inspect.ismethod(realobj)
                     and realobj.__func__ is obj)):
            raise Exception('%s.%s (%r) is not %r!' % (
                    namespace, simicsdoc.name, realobj, obj))

    o.print_end(ofile)
    ofile.close()
