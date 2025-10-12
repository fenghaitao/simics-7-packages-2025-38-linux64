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

import sys, inspect
import os

try:
    import api_help_py
except ImportError:
    # may happen during build
    api_help_py = None

_rewrite_doc_strings = (
    api_help_py
    and os.environ.get("SIMICS_DONT_REWRITE_PYDOC", None) is None
)

string_types = (str, bytes)

class SimicsDocEntry:
    def __init__(self, module, namespace, name, short, body, example,
                 exceptions, see_also, return_value, synopsis, doc_id,
                 docu_suffix, is_function, context):
        self.module       = module
        self.namespace    = namespace
        self.name         = name
        self.short        = short
        self.body         = body
        self.example      = example
        self.exceptions   = exceptions
        self.see_also     = see_also
        self.return_value = return_value
        self.synopsis     = synopsis
        self.doc_id       = doc_id
        self.docu_suffix  = docu_suffix
        self.is_function  = is_function
        self.context      = context


# read from api_help
_simics_doc_items = set()

def doc(short, *, module = None, namespace = '', name = None,
        example = None, exceptions = None, see_also = None, return_value = None,
        synopsis = None, doc_id = None, docu_suffix = '',
        context = None, metaclass = type):
    """Decorator and metaclass that adds the decorated object (function or
    class) to the Simics reference documentation, api-help, and Python's
    help().

    'module' can optionally be set to the name of the module where the
    object is defined. Any "_impl" suffix will be dropped.

    'namespace' can optionally be set to the namespace (within the
    module) that the object can be found in. Must be set for any
    objects defined inside classes.

    By default, the decorated object's __name__ attribute is used for the
    object's name. You can override that by setting 'name'.

    The object must have a documentation string that may use CLI markup.
    'short' is used as the short description in the reference documentation.

    The optional fields 'context', 'example', 'see_also', and 'return_value'
    may be set to add such documentation fields.

    You can override the synopsis by setting 'synopsis' to a string, or leave
    it out by setting it to False.

    By default, the documentation will be added to the "simics api python" docu
    group. This can be overridden by setting '__simicsapi_doc_id__' in the
    defining module, or by setting 'doc_id'.

    'docu_suffix' can be set to a string that will be inserted before
    the closing </add> tag in docu output.

    If a documented class needs a "real" metaclass, set 'metaclass' to it.

    For functions add @doc(...) as a function decorator. For classes,
    use doc(...) value as a metaclass of the class to be documented."""

    class docmetaclass(metaclass):
        def __new__(meta, *args):

            def get_doc_id(doc_id, mod):
                if doc_id:
                    return doc_id

                pymod = sys.modules.get(mod)
                return ((pymod and getattr(pymod, '__simicsapi_doc_id__',
                                           None))
                        or 'simics api python')

            if len(args) == 1:
                # used as function decorator
                (f,) = args
                is_function = inspect.isfunction(f)
                assert is_function
                getter = lambda a: getattr(f, a)
                setter = lambda a, v: setattr(f, a, v)
                real_name = name or f.__name__
                finish = lambda: f
            else:
                # used as metaclass
                classname, bases, classdict = args
                if synopsis is None:
                    raise Exception(("%r is no function; you need to set"
                                     " 'synopsis' in call to doc()") % (classname,))
                is_function = False
                getter = classdict.__getitem__
                setter = classdict.__setitem__
                real_name = name or classname
                finish = lambda: metaclass.__new__(
                    metaclass, classname, bases, classdict)

            body = getter('__doc__')
            if not isinstance(body, string_types):
                raise Exception('%s: has no documentation (__doc__ field)' % (
                        real_name,))

            real_module = module
            if real_module is None:
                real_module = getter('__module__')
            real_doc_id = get_doc_id(doc_id, real_module)
            if real_module.endswith('_impl'):
                real_module = real_module[:-5]
            setter('__simicsdoc__', SimicsDocEntry(
                real_module, namespace, real_name,
                short, body, example, exceptions, see_also,
                return_value, synopsis, real_doc_id, docu_suffix,
                is_function, context))

            if _rewrite_doc_strings:
                doc = api_help_py.api_help_py.get('%s.%s' % (
                        real_module, real_name))
                if doc:
                    setter('__doc__', doc[1])

            r = finish()
            _simics_doc_items.add(r)
            return r

    return docmetaclass
