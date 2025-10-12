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


from simicsutils.internal import ensure_text

class DetectException(Exception): pass

class ElfParser:
    def __init__(self, tcf_iface, symbol_file):
        self.__tcf_iface = tcf_iface
        (ok, ret) = tcf_iface.open_symbol_file(symbol_file, 0)
        if not ok:
            raise DetectException("%s: %s" % (symbol_file, ret))
        self.__elf_id = ret
        # Cache symbols and offsets here because tcf_iface is leaking
        # memory (shared bug 501217). It's also faster since we don't
        # have to jump in and out of C
        self.__cache = {}
    def get_symbol_info(self, name):
        if name in self.__cache:
            return self.__cache.get(name)
        return self.__cache.setdefault(
            name, self.__tcf_iface.get_symbol_info(self.__elf_id, name))
    def get_field_offset(self, struct_name, field_name):
        if (struct_name, field_name) in self.__cache:
            return self.__cache.get((struct_name, field_name))
        return self.__cache.setdefault(
            (struct_name, field_name),
            self.__tcf_iface.get_field_offset(
                self.__elf_id, struct_name, field_name))
    def close(self):
        self.__tcf_iface.close_symbol_file(self.__elf_id)

class PlainParser:
    def __init__(self, symbol_file):
        self.__symbol_file = symbol_file
        self.__symbols = {}
        with open(symbol_file, 'rb') as f:
            for (nr, line) in enumerate(f.readlines(), 1):
                try:
                    items = line.split()
                    if not items:
                        continue
                    (addr, size, sym_type, name, module) =  [None] * 5
                    if len(items) == 2:
                        (sym_type, name) = items
                    elif len(items) == 3:
                        (addr, sym_type, name) = items
                    elif len(items) == 4:
                        if (items[3].startswith(b'[')
                            and items[3].endswith(b']')):
                            # /proc/kallsyms format
                            (addr, sym_type, name, module) = items
                        else:
                            (addr, size, sym_type, name) = items
                    else:
                        self.__raise_error(nr, line)
                    self.__symbols[ensure_text(name)] = [
                        None if addr is None else int(addr, 16),
                        None if size is None else int(size, 16)]
                except ValueError:
                    self.__raise_error(nr, line)
    def __raise_error(self, nr, line):
        raise DetectException(
            "Failed parsing plain symbol file '%s', line %d: %r\n" % (
                self.__symbol_file, nr, line))

    def get_symbol_info(self, name):
        symbol_info = self.__symbols.get(name)
        if symbol_info is not None:
            return [True, symbol_info]
        return [False, "Symbol not found"]
    def get_field_offset(self, struct_name, field_name):
        return [False, "Not supported with plain parser"]
    def close(self):
        pass
