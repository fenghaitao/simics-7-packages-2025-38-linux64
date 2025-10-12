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


# A "node path" is a convenient way to specify nodes in a software
# tracker by the values of their properties. The routines in this file
# are intended to be used by CLI commands that wish to parse node path
# arguments.

import re
import itertools as it
import unittest
import ast
import cli
import cli_impl
import simics
from simmod.os_awareness import common

(r_ident, r_ident_all) = [re.compile(r'[a-zA-Z_][0-9a-zA-Z_]*' + s)
                          for s in ['', '$']]

class NodePathNode:
    def __init__(self, node_id, props, get_parent):
        self.node_id = node_id
#        self.props = props
        self.parent = get_parent
        self.get = props.get


class Token:
    def __init__(self, m):
        self.string = m.group(0)
    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.string)
    def __str__(self):
        return self.string
    def val(self):
        return self.string

class TIdent(Token): pass
class TElide(Token): pass
class TAsterisk(Token): pass
class TEquals(Token): pass
class TSlash(Token): pass
class TComma(Token): pass
class TInt(Token):
    def val(self):
        return self.integer
class TDecimalInt(TInt):
    def __init__(self, m):
        Token.__init__(self, m)
        self.integer = int(self.string, 10)
class THexInt(TInt):
    def __init__(self, m):
        Token.__init__(self, m)
        self.integer = int(self.string, 16)
class TString(Token):
    def __init__(self, s):
        self.string = s

# Tokenize a string.
class tokenizer:
    matchers = [
        (re.compile(r'0[xX][0-9a-fA-F]+'), THexInt),
        (re.compile(r'[0-9]+'), TDecimalInt),
        (r_ident, TIdent),
        (re.compile(r'/\*\*/'), TElide),
        (re.compile(r'\*'), TAsterisk),
        (re.compile('='), TEquals),
        (re.compile('/'), TSlash),
        (re.compile(','), TComma)]
    def __init__(self, s):
        self.s = s

    # Return the next token, or None if there is no next token.
    def next(self):
        if not self.s:
            return None
        for (r,c) in self.matchers:
            m = r.match(self.s)
            if m:
                self.s = self.s[m.end(0):]
                return c(m)
        if self.s.startswith("'"):
            i = 1
            while i < len(self.s):
                if self.s[i] == "'":
                    tok = TString(ast.literal_eval(self.s[:i+1]))
                    self.s = self.s[i+1:]
                    return tok
                if self.s[i] == '\\':
                    i+= 1
                i += 1
            raise NodePathError('Malformed string')
        raise NodePathError("Garbage at end: %r" % self.s)


class NodePathError(Exception): pass

def fmt_value(v):
    if isinstance(v, str):
        if r_ident_all.match(v):
            return v
        else:
            return repr(v)
    else:
        return str(v)

def expect(got, wanted):
    if not isinstance(got, wanted):
        raise NodePathError("Expected %s, got %r" % (wanted.__name__, got))

# Represents a constraint on a single property of a single node.
# pred(s, prefix) is a function that accepts or rejects the string s
# (prefix = False), or any string starting with s (prefix = True). rep
# is the human-readable string representation of pred.
class NodePathRule:
    def __init__(self, key, pred, rep):
        assert isinstance(key, str)
        assert callable(pred)
        assert isinstance(rep, str)
        self.key = key
        self.pred = pred
        self.rep = rep

    def __repr__(self): return "NodePathRule(%r, %r)" % (self.key, self.rep)
    def __str__(self): return "%s=%s" % (self.key, self.rep)

    # Test whether the given node meets the constraint.
    def match(self, node):
        return node.match(self.key, self.pred)

    # Test whether the rule is for the key "name", and the expected
    # value is suitable as an identifier.
    def is_simple_name_rule(self):
        return self.key == 'name' and r_ident_all.match(self.rep)

# Represents constraints on zero or more properties of a single node.
# If elide is true, the constraints may be satisfied by the given node
# or any of its descendants; if elide is false, only the node itself
# will do.
class NodePathFilter:
    def __init__(self, filter, elide):
        self.rules = filter
        self.elide = elide

    def __repr__(self):
        return 'NodePathFilter(%r, %r)' % (self.rules, self.elide)

    def __str__(self):
        if not self.rules:
            s = "*"
        elif len(self.rules) == 1 and self.rules[0].is_simple_name_rule():
            s = self.rules[0].rep
        else:
            s = ",".join(str(f) for f in self.rules)
        if self.elide:
            s = "/**/" + s
        else:
            s = "/" + s
        return s

    # Test whether the given node meets the constraints. Note: the
    # value of elide is not taken into account.
    def match(self, node):
        if self.rules is None or all(rule.match(node) for rule in self.rules):
            return node
        return None

# Represents constraints on the properties of a node and its ancestors.
class NodePathPattern:
    def __init__(self, elts):
        self.filters = elts

    def __repr__(self):
        return 'NodePathPattern(%r)' % (self.filters)

    def __str__(self):
        s = "".join(str(e) for e in self.filters)
        if s.startswith('/**/'):
            s = s[4:]
        return s

    # Find all nodes whose list of ancestors (starting with
    # start_node, ending with the node itself) meets the constraints.
    def find_all(self, start_node):
        current = [start_node]
        matching = []
        filters = list(self.filters)
        while filters:
            matching = []
            next = []
            seen = set()
            filt = filters.pop(0)
            while current:
                n = current.pop(0)
                if filt.elide:
                    current.extend(n.children())
                m = filt.match(n)
                if m is not None and m not in seen:
                    seen.add(m)
                    matching.append(m)
                    next.extend(m.children())
            current = next
        return iter(matching)

    # Return an arbitrary node whose list of ancestors (starting with
    # start_node, ending with the node itself) meets the constraints.
    # If no such node exists, return None.
    def find(self, start_node):
        try:
            return next(self.find_all(start_node))
        except StopIteration:
            return None

    # Test whether the given node and its ancestors meet the
    # constraints.
    def match(self, node, filters=None):
        if filters is None:
            filters = list(self.filters)
        #print "match", node, filters
        if not filters[-1].match(node):
            return False
        if filters[-1].elide:
            if len(filters) == 1:
                return True
            parent = node.parent()
            ancestors = []
            while parent is not None:
                ancestors.append(parent)
                parent = parent.parent()
            return any(self.match(n, filters[:-1]) for n in ancestors)
        else:
            return self.match(node.parent(), filters[:-1])

node_spec_t = cli.poly_t('node spec', cli.str_t, cli.uint_t)

class NodeTraverse:
    def __init__(self, osa_obj, node_id):
        self.nt_query = common.get_node_tree_query(osa_obj)
        self.osa_obj = osa_obj
        self.node_id = node_id
        self.props = self.nt_query.get_node(node_id)
        if not self.props:
            raise NodePathError("Invalid node id: %d" % node_id)
        self.get = self.props.get
        self.formatted_props = self.nt_query.get_formatted_properties(node_id)
        if self.formatted_props is None:
            raise NodePathError(
                "Unable to get formatted props for node: %d" % node_id)
    def match(self, key, pred):
        """Return true if the predicate function accepts the node
        property with the given key."""
        try:
            v = self.node_id if key == 'id' else self.props[key]
            vf = self.node_id if key == 'id' else self.formatted_props[key]
        except KeyError:
            return False
        # Is v just a prefix of the "true" value?
        max_name_length = self.get_max_name_length()
        prefix = (key == 'name' and max_name_length is not None
                  and len(v) >= max_name_length)
        return pred(v, prefix) or pred(vf, prefix)
    def children(self):
        return (NodeTraverse(self.osa_obj, nid)
                for nid in self.nt_query.get_children(self.node_id))
    def parent(self):
        parent_id = self.nt_query.get_parent(self.node_id)
        if parent_id is not None:
            return NodeTraverse(self.osa_obj, parent_id)
        else:
            return None

    def get_nodepath_node(self):
        return NodePathNode(
            self.node_id, self.props, self.get_parent_nodepath_node)

    def get_parent_nodepath_node(self):
        parent = self.parent()
        if parent is None:
            return None
        return parent.get_nodepath_node()

    def get_max_name_length(self):
        max_len = self.props.get('max_name_length')
        if max_len is not None:
            return max_len

        parent = self.parent()
        if parent is not None:
            return parent.get_max_name_length()
        return None

def find_all_nodes(sw, root_id, node_spec):
    if isinstance(node_spec, int):
        # Only yield the node number if it is valid
        if common.get_node_tree_query(sw).get_node(node_spec):
            yield node_spec
    else:
        for n in node_spec.find_all(NodeTraverse(sw, root_id)):
            yield n.node_id

# Given a string containing an integer, return the corresponding
# integer; given a string containing a node path, return a NodePathPattern
# object.
def parse_node_spec(node_spec):
    try:
        return int(node_spec)
    except ValueError:
        pass
    return from_string(node_spec)

def get_all_matching_nodes(sw, root_id, ns):
    all_matching = list(find_all_nodes(sw, root_id, ns))
    return all_matching

# Given a first token (tok) and a tokenizer (tg) that produces the
# remaining tokens, parse the tokens as a node path pattern; return
# the first unused token (or None, if the tokenizer was exhausted),
# and the node path pattern.
def parse_path(tg, tok):
    path = []
    while isinstance(tok, (TSlash, TElide)):
        (tok, filt) = parse_filter(tg, tok)
        path.append(filt)
    return (tok, NodePathPattern(path))

# Given a first token (tok) and a tokenizer (tg) that produces the
# remaining tokens, parse the tokens as a node path filter; return
# the first unused token (or None, if the tokenizer was exhausted),
# and the node path filter.
def parse_filter(tg, tok):
    if isinstance(tok, TSlash):
        elide = False
    elif isinstance(tok, TElide):
        elide = True
    else:
        assert False
    tok = tg.next()
    filter = []
    if isinstance(tok, (TIdent, TAsterisk)):
        while True:
            (tok, r) = parse_rule(tg, tok)
            if r:
                filter.append(r)
            if isinstance(tok, TComma):
                tok = tg.next()
            else:
                break
        return tok, NodePathFilter(filter, elide)
    raise NodePathError("Empty rule")

# Given a first token (tok) and a tokenizer (tg) that produces the
# remaining tokens, parse the tokens as a node path rule; return the
# first unused token (or None, if the tokenizer was exhausted), and
# the NodePathRule (or None, for wildcard rules).
def parse_rule(tg, tok):
    def merge(toks):
        if not toks:
            raise NodePathError("Empty rule")
        for i in range(1, len(toks)):
            if all(isinstance(t, TAsterisk) for t in toks[i-1:i+1]):
                raise NodePathError("Double stars in wildcard")
        if len(toks) == 1 and isinstance(toks[0], TInt):
            v = toks[0].val()
            return (lambda x, prefix: x == v, str(v))

        # We don't support concatenating integers with other things,
        # since that would require us to stringify them, and there's
        # no unique way to do that (hex vs. decimal, for example).
        if any(isinstance(t, TInt) for t in toks):
            raise NodePathError('Integer value must be quoted here')

        # At index j, we have the matcher for prefixes of length j.
        lim_prefix_matchers = [lambda x: True]

        # Matcher for prefixes of length >= len(lim_prefix_matchers).
        unlim_prefix_matcher = None

        r = []
        for t in toks:
            if isinstance(t , TAsterisk):
                r.append('.*')
                if not unlim_prefix_matcher:
                    # When we see the first asterisk, we're done with
                    # the limited-length prefix matchers, and can
                    # define the unlimited-length prefix matcher.
                    unlim_prefix_matcher = re.compile(''.join(r) + '$').match
            else:
                for c in t.string:
                    r.append(r'\x%02x' % ord(c))
                    if not unlim_prefix_matcher:
                        # We've seen j tokens, all literal characters.
                        # This lets us define the matcher for prefixes
                        # of length j, and store it at index j in the list.
                        lim_prefix_matchers.append(
                            re.compile(''.join(r) + '$').match)
        # We've seen all tokens, so define the matcher for complete strings.
        complete_matcher = re.compile(''.join(r) + '$').match
        if not unlim_prefix_matcher:
            # All tokens were literal characters. That means that
            # prefixes longer than the number of tokens will never
            # match.
            unlim_prefix_matcher = lambda x: False

        def rmatch(x, prefix):
            x = str(x)
            if not prefix:
                return complete_matcher(x)
            if len(x) < len(lim_prefix_matchers):
                return lim_prefix_matchers[len(x)](x)
            return unlim_prefix_matcher(x)
        s = []
        for t in toks:
            if isinstance(t, TAsterisk):
                s.append(None)
                continue
            if not s or s[-1] is None:
                s.append('')
            s[-1] += t.string
        return (rmatch, ''.join('*' if x is None else x if r_ident_all.match(x)
                                else repr(x) for x in s))
    left = []
    ttypes = (TAsterisk, TString, TInt, TIdent)
    while isinstance(tok, ttypes):
        left.append(tok)
        tok = tg.next()
    if not isinstance(tok, TEquals):
        if len(left) == 1 and isinstance(left[0], TAsterisk):
            return (tok, None)
        return (tok, NodePathRule('name', *merge(left)))
    tok = tg.next() # discard equals sign
    if len(left) != 1:
        raise NodePathError("Rule doesn't start with a key")
    [left] = left
    if isinstance(left, TAsterisk):
        raise NodePathError("Wildcard in rule key")
    right = []
    while isinstance(tok, ttypes):
        right.append(tok)
        tok = tg.next()
    return (tok, NodePathRule(left.string, *merge(right)))

# Parse a string as a node path pattern.
def from_string(s):
    if not s:
        raise NodePathError("Empty path")

    if not s.startswith('/'):
        s = '/**/' + s
    tg = tokenizer(s)
    (tok, path) = parse_path(tg, tg.next())
    if tok:
        raise NodePathError("Garbage at end: %s" % tok)
    return path

# Return a string representation of the given node, on a form that can
# be parsed into a NodePathFilter that matches the node.
def node_path_element(node_tree, node, force_name=False):
    assert isinstance(node, NodePathNode)
    name = node.get('name')
    if not name:
        raise NodePathError("Node %d does not have a name." % node.node_id)
    if not isinstance(name, str):
        raise NodePathError("Node %d does not have a valid name."
                            % node.node_id)
    keys = sorted(node.get('extra_id') or ())
    if not keys:
        keys = ['name']
    elif force_name and 'name' not in keys:
        keys[0:0] = ['name']
    nt_query = node_tree.iface.osa_node_tree_query
    props = nt_query.get_formatted_properties(node.node_id)
    if keys == ['name'] and r_ident_all.match(node.get('name')):
        return fmt_value(props['name'])
    # Call fmt_value for all properties to make sure the value is a node path
    # value. Elements with special characters in them must be quoted to
    # distinguish them from wild cards or other node path pattern delimiters.
    return ",".join("%s=%s" % (k, fmt_value(props[k])) for k in keys)

# Return a string representation of the given node and the sequence of
# ancestors leading up to it, on a form that can be parsed into a
# NodePathPattern that matches the node.
def node_path(node_tree, node):
    assert isinstance(node, NodePathNode)

    s = "/" + node_path_element(node_tree, node)
    parent = node.parent()
    if parent is not None:
        s = node_path(node_tree, parent) + s
    return s

class TestParseFormat(unittest.TestCase):
    def test_autoelide(self):
        self.assertEqual(str(from_string("a=1")), "a=1")
    def test_start1(self):
        self.assertEqual(str(from_string("/a=1")), "/a=1")
    def test_start2(self):
        self.assertEqual(str(from_string("/**/a=1")), "a=1")
    def test_2(self):
        self.assertEqual(str(from_string("a=1/b=x")), "a=1/b=x")
    def test_3(self):
        self.assertEqual(str(from_string("a=1/**/b=x")), "a=1/**/b=x")
    def test_5(self):
        self.assertEqual(str(from_string("/*/a=1")), "/*/a=1")
    def test_6(self):
        self.assertEqual(str(from_string("a='i/o'")), "a='i/o'")
    def test_7(self):
        self.assertEqual(str(from_string(r"a='i\n/o'")), r"a='i\n/o'")
    def test_8(self):
        self.assertEqual(str(from_string(r"a=1,b=2")), r"a=1,b=2")
    def test_9(self):
        self.assertEqual(str(from_string(r"a=0xff,b=0x10")), r"a=255,b=16")
    def test_10(self):
        self.assertEqual(str(from_string(r"a='0xff',b='10'")),
                          r"a='0xff',b='10'")
    def test_11(self):
        self.assertEqual(str(from_string(r"a=f*ck")), r"a=f*ck")
    def test_12(self):
        self.assertEqual(str(from_string(r"a=*a*b*c*")), r"a=*a*b*c*")
    def test_13(self):
        self.assertEqual(str(from_string(r"x")), r"x")

class TestParseError(unittest.TestCase):
    def test_error_1(self):
        self.assertRaises(NodePathError, from_string, "a b")
    def test_error_2(self):
        self.assertRaises(NodePathError, from_string, "a,")
    def test_error_3(self):
        self.assertRaises(NodePathError, from_string, "a,,")
    def test_error_4(self):
        self.assertRaises(NodePathError, from_string, "//")
    def test_error_5(self):
        self.assertRaises(NodePathError, from_string, "a//b")
    def test_error_6(self):
        self.assertRaises(NodePathError, from_string, "a/b/")
    def test_error_7(self):
        self.assertRaises(NodePathError, from_string, "a/**/")
    def test_error_8(self):
        self.assertRaises(NodePathError, from_string, "a/**")
    def test_error_9(self):
        self.assertRaises(NodePathError, from_string, "**/a")

class TestNode:
    o = {}
    def __init__(self, node_tree, i, properties, *children):
        self.o[i] = self
        self.i = i
        self.get = properties.get
        self.props = properties
        self.children = lambda: children
        for c in children:
            c.parent = lambda: self
        nt_query = node_tree.iface.osa_node_tree_query
        self.formatted_props = nt_query.get_formatted_properties(self.i)
    def __repr__(self): return "N(%d)" % self.i
    def parent(self): return None
    def match(self, key, pred):
        v = self.get(key)
        vf = self.i if key == 'id' else self.formatted_props.get(key)
        if v is None and vf is None:
            return False
        return pred(v, None) or pred(vf, None)
    def get_nodepath_node(self):
        return NodePathNode(self.i, self.props, self.get_parent_nodepath_node)
    def get_parent_nodepath_node(self):
        parent = self.parent()
        if parent is None:
            return None
        return parent.get_nodepath_node()

class TestFind(unittest.TestCase):
    def setUp(self):
        class N(TestNode): pass
        t = MockNodeTree(N.o)
        self.tree = N(t, 1, { 'a': 1 },
                      N(t, 2, { 'a': 2, 'b': 1 },
                        N(t, 4, { 'a': 4 },
                          N(t, 6, { 'a': 6 }))),
                      N(t, 3, { 'a': 3, 'b': 1 },
                        N(t, 5, { 'a': 5 })))
        self.nodes = N.o

    def test_find_all_01(self):
        p = from_string("/*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [1])

    def test_find_all_02(self):
        p = from_string("/a=1")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [1])

    def test_find_all_03(self):
        p = from_string("/**/a=1")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [1])

    def test_find_all_04(self):
        p = from_string("a=1")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [1])

    def test_find_all_05(self):
        p = from_string("a=2")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2])

    def test_find_all_06a(self):
        p = from_string("/*/*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2, 3])

    def test_find_all_06b(self):
        p = from_string("*/*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2, 3, 4, 5, 6])

    def test_find_all_06c(self):
        p = from_string("*/**/*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2, 3, 4, 5, 6])

    def test_find_all_06d(self):
        p = from_string("*/**/*/**/*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [4, 5, 6])

    def test_find_all_07(self):
        p = from_string("*")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [1, 2, 3, 4, 5, 6])

    def test_find_all_08(self):
        p = from_string("a=1/a=2")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2])

    def test_find_all_09(self):
        p = from_string("a=1/**/a=4")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [4])

    def test_find_all_10(self):
        p = from_string("/**/a=2,b=1")
        nodes = [n.i for n in p.find_all(self.tree)]
        self.assertEqual(nodes, [2])

    def test_match_01(self):
        p = from_string("a=3")
        self.assertTrue(p.match(self.nodes[3]))
        self.assertFalse(p.match(self.nodes[4]))

    def test_match_02(self):
        p = from_string("a=1/**/a=4")
        finds = list(p.find_all(self.tree))
        for i,n in sorted(self.nodes.items()):
            self.assertEqual(p.match(n), n in finds)

    def test_match_03(self):
        p = from_string("a=3/*")
        self.assertFalse(p.match(self.nodes[3]))
        self.assertTrue(p.match(self.nodes[5]))

class TestFindGlob(unittest.TestCase):
    def setUp(self):
        class N(TestNode): pass
        t = MockNodeTree(N.o)
        self.tree = N(t, 0, { 'a': 'abcd', 'name': 'sooty' },
                      N(t, 1, { 'a': 'abc', 'name': 'bloody' }),
                      N(t, 2, { 'a': 'ab' }),
                      N(t, 3, { 'b': 'f*ck' }),
                      N(t, 4, { 'b': 'fick'}))

    def find_all(self, pattern, expected):
        self.assertEqual(
            [n.i for n in from_string(pattern).find_all(self.tree)],
            expected)

    def test00(self): self.find_all(r"a=abc*", [0, 1])
    def test01(self): self.find_all(r"a=*b", [2])
    def test02(self): self.find_all(r"/a=abc*", [0])
    def test03(self): self.find_all(r"/*/a=abc*", [1])
    def test04(self): self.find_all(r"a=*", [0, 1, 2])
    def test05(self): self.find_all(r"b=f*ck", [3, 4])
    def test06(self): self.find_all(r"b='f*ck'", [3])
    def test07(self): self.find_all(r"a='a*'", [])
    def test08(self): self.find_all(r"*b*", [1])
    def test09(self): self.find_all(r"*oo*", [0, 1])
    def test10(self): self.find_all(r"*oo*/*oo*", [1])
    def test11(self): self.find_all(r"*", [0, 1, 2, 3, 4])
    def test12(self): self.find_all(r"name=*", [0, 1])
    def test13(self): self.find_all(r"name='blood'*", [1])
    def test14(self): self.find_all(r"name='blo'*'y'", [1])
    def test15(self): self.find_all(r"name='blo'*'z'", [])
    def test16(self): self.find_all(r"name='blo'*'d'*", [1])
    def test17(self): self.find_all(r"name='blo1'*'y'", [])
    def test18(self): self.find_all(r"a=5", [])
    def test19(self):
        self.assertRaises(NodePathError, self.find_all, r"a=5*", [])
    def test20(self): self.find_all(r"a='5'*", [])

# Test glob matching with properties truncated at length 5.
class TestFindGlobMaxlen(unittest.TestCase):
    def setUp(self):
        class N(TestNode):
            def match(self, key, pred):
                v = self.get(key)
                if v is None:
                    return False
                assert len(v) <= 5
                return pred(v, len(v) == 5)
        t = MockNodeTree(N.o)
        self.tree = N(t, 0, { 'a': 'abcde', 'b': 'fgh' })
    def find_all(self, pattern, expected):
        self.assertEqual(
            [n.i for n in from_string(pattern).find_all(self.tree)],
            expected)

    def test0(self): self.find_all(r"a=abc*", [0])
    def test1(self): self.find_all(r"a=abcde", [0])
    def test2(self): self.find_all(r"a=abcdef", [0])
    def test3(self): self.find_all(r"a=abcd", [])
    def test4(self): self.find_all(r"a=*G", [0])
    def test5(self): self.find_all(r"b=fg*", [0])
    def test6(self): self.find_all(r"b=fgh", [0])
    def test7(self): self.find_all(r"b=fghi", [])
    def test8(self): self.find_all(r"b=fg", [])
    def test9(self): self.find_all(r"b=*G", [])

class MockNodeTree:
    def __init__(self, nodes):
        self.nodes = nodes
    def get_formatted_properties(self, node_id):
        return {key: value[::-1] if key == "rev" else value
                for (key, value) in self.nodes[node_id].props.items()}

    @property
    def iface(self):
        return self
    @property
    def osa_node_tree_query(self):
        return self

class TestPath(unittest.TestCase):
    def setUp(self):
        class N(TestNode): pass
        self.nodes = N.o
        self.node_tree = MockNodeTree(N.o)
        t = self.node_tree
        self.root_id = 1
        self.tree = N(t, self.root_id, { 'name': 'A', 'a': 1 },
                      N(t, 2, { 'name': 'A B', 'a': 2, 'b': 1 },
                        N(t, 4, { 'name': 'AB C', 'a': 4 },
                          N(t, 6, { 'name': 'ABC D', 'a': 6 }))),
                      N(t, 3, { 'name': 'A E', 'a': 3, 'b': 1 },
                        N(t, 5, { 'name': 'AE F', 'a': 5 },
                          N(t, 7, { 'name': "Reverse", 'a': 7, 'rev': "test",
                                 'extra_id': ['rev']}))))

    def test_node_path_01(self):
        p = from_string("a=1")
        self.assertEqual(node_path(
                self.node_tree, p.find(self.tree).get_nodepath_node()), "/A")

    def test_node_path_02(self):
        p = from_string("a=2")
        self.assertEqual(node_path(
                self.node_tree, p.find(self.tree).get_nodepath_node()),
                         "/A/name='A B'")

    def test_node_path_03(self):
        p = from_string("a=7")
        pretty_nodepath = "/A/name='A E'/name='AE F'/rev=tset"
        self.assertEqual(node_path(
                self.node_tree, p.find(self.tree).get_nodepath_node()),
                         pretty_nodepath)
        spec = from_string(pretty_nodepath)
        node = spec.find(self.tree)
        self.assertTrue(node)

def register_osa_node_path_interface(classname):
    np_iface = simics.osa_node_path_interface_t()
    np_iface.matching_nodes = np_iface_matching_nodes
    np_iface.node_path = np_iface_node_path
    simics.SIM_register_interface(classname, "osa_node_path", np_iface)

def np_iface_matching_nodes(obj, root_id, node_path_pattern):
    if not obj.requests:
        return [False, "Tracker not enabled"]

    roots = obj.iface.osa_node_tree_query.get_root_nodes()
    if root_id not in roots:
        return [False, "Invalid root id"]
    try:
        ns = parse_node_spec(node_path_pattern)
    except NodePathError as e:
        return [False, str(e)]

    matching = get_all_matching_nodes(obj, root_id, ns)
    return [True, matching]

def np_iface_node_path(obj, node_id):
    if not obj.requests:
        return [False, "Tracker not enabled"]

    try:
        np_node = NodeTraverse(obj, node_id).get_nodepath_node()
    except NodePathError as e:
        return [False, str(e)]
    return [True, str(node_path(obj, np_node))]
