# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


class KeyValuePrettyPrinter:
    '''Prints a human readable representation of a list containing
    key-value pairs. For this to work, the key-enums used, need
    to be described in the key_to_string_dict which converts the
    enum value to the suitable string definition.'''

    def __init__(self, key_to_string_dict):
        self._key_to_string_dict = key_to_string_dict
        self._result_string = ""
        self._debug = False

    def result(self, lst):
        self._result_string = ""
        self._pp(lst)
        self._pr("\n")
        return self._result_string

    def _shallow(self, elem):
        return not isinstance(elem, (tuple, list))

    def _all_shallow(self, lst):
        for l in lst:
            if not self._shallow(l):
                return False
        return True

    @staticmethod
    def _rep(x):
        '''prints strings within qouts'''
        if isinstance(x, str):
            return f'"{x}"'
        return str(x)

    def _pr(self, s):
        self._result_string += s
        if self._debug:
            print(s, end="")

    def _pp_iter(self, lst, indent, start, stop):
        self._pr((" " * indent) + start + "\n")
        for i, t in enumerate(lst):
            if i > 0:
                self._pr(",\n")
            self._pp(t, indent + 1)
        self._pr("\n" + (" " * indent) + stop)

    def _pp_iter_shallow(self, lst, indent, start, stop):
        self._pr((" " * indent) + start)
        s = [self._rep(x) for x in lst]
        self._pr(", ".join(s))
        self._pr(stop)

    def _key_for_key_value_pair(self, lst):
        if (isinstance(lst, (list, tuple))
            and len(lst) == 2
            and isinstance(lst[0], int)
            and lst[0] in self._key_to_string_dict):
            return self._key_to_string_dict[lst[0]]
        return None

    def _pp(self, kv_list, indent=0):
        key = self._key_for_key_value_pair(kv_list)
        if key:
            self._pr(f"{' ' * indent}({key}, ")
            if self._shallow(kv_list[1]):
                self._pr(self._rep(kv_list[1]) + ")")
            else:
                self._pr("\n")
                self._pp(kv_list[1], indent + 2)
                self._pr(f"\n{' ' * indent})")

        elif isinstance(kv_list, list):
            if self._all_shallow(kv_list):
                self._pp_iter_shallow(kv_list, indent, "[", "]")
            else:
                self._pp_iter(kv_list, indent, "[", "]")
        elif isinstance(kv_list, tuple):
            if self._all_shallow(kv_list):
                self._pp_iter_shallow(kv_list, indent, "(", ")")
            else:
                self._pp_iter(kv_list, indent, "(", ")")
        else:
            self._pr((" " * indent) + self._rep(kv_list))
