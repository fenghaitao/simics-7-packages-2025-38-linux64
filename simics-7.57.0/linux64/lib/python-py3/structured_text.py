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
import io

# This is what man uses
LEFT_MARGIN = 7


class StructuredText(object):
    """Formats structured text for Simics CLI."""

    def __init__(self, out, width=80):
        self.line_prefix = LEFT_MARGIN * " "
        self.column = 0
        self.width = width
        self.at_p_boundary = True
        self.at_line_start = True
        self.space_needed = False
        self.out = out

    def format(self, nodes):
        self._format(nodes)
        self.newline()

    def _format(self, nodes):
        for n in nodes:
            if isinstance(n, str):
                self.text(n)
            elif n["tag"] == "code":
                # Mark up fixed-width as bold as we want it highlighted.
                self.start_bold()
                self.text(n["code"])
                self.end_bold()
            elif n["tag"] == "p":
                self.start_p()
                self._format(n["children"])
                self.end_p()
            elif n["tag"] == "em":
                self.start_italics()
                self._format(n["children"])
                self.end_italics()
            elif n["tag"] == "strong":
                self.start_bold()
                self._format(n["children"])
                self.end_bold()
            elif n["tag"] == "li":
                self.start_item()
                self._format(n["children"])
                self.end_item()
            elif n["tag"] in ["list"]:
                # Both ordered and unordered lists are handled the same
                for item in n["items"]:
                    self.start_item()
                    self._format(item)
                    self.end_item()
            elif n["tag"] == "blockquote":
                self.start_quote()
                self._format(n["children"])
                self.end_quote()
            elif n["tag"] == "pre":
                self.blank_line()
                text = n["code"]
                # Write each line with the prefix.
                # Strip whitespace at the end to avoid superfluous newlines.
                # Whitespace at the start may be important, so keep it there.
                self.write_lines(text.rstrip())
                self.blank_line()
            elif n["tag"] in ["a", "s", "img"]:
                # These tags just show up as their content
                self._format(n["children"])
            elif n["tag"] == "br":
                self.newline()
            elif n["tag"] == "hr":
                self.blank_line()
                self.pr("─" * (self.width - len(self.line_prefix)))
                self.blank_line()
            elif n["tag"] == "task":
                if n["completed"]:
                    self.pr("[x]")
                    self.space_needed = True
                else:
                    self.pr("[ ]")
                    self.space_needed = True
            elif n["tag"] == "table":
                import table
                import cli

                def td_to_string(td):
                    sio = io.StringIO()
                    sub_formatter = StructuredText(sio, width=10000)
                    sub_formatter._format(td)
                    return sio.getvalue()

                columns = [
                    [
                        (table.Column_Key_Name, td_to_string(c["header"])),
                        (table.Column_Key_Alignment, c["alignment"] or "left"),
                    ]
                    for c in n["columns"]
                ]
                props = [(table.Table_Key_Columns, columns)]
                data = [[td_to_string(td) for td in tr] for tr in n["rows"]]
                self.blank_line()
                try:
                    tbl = table.Table(props, data).to_string(
                        border_style="thin",
                        no_row_column=True,
                        force_max_width=self.width - len(self.line_prefix),
                    )
                    self.write_lines(tbl.strip())
                except cli.CliError as e:
                    err = str(e)
                    self.text(err)
                self.blank_line()
            elif n["tag"] in ["h1", "h2"]:
                n = upper_case(n)
                self.blank_line()
                self.pop(" " * LEFT_MARGIN)
                self.start_bold()
                self._format(n["children"])
                self.end_bold()
                self.push(" " * LEFT_MARGIN)
                self.newline()
                self.at_p_boundary = True
            elif n["tag"] in ["h3", "h4"]:
                self.blank_line()
                self.pop(" " * 4)
                if n["tag"] == "h3":
                    self.start_bold()
                self._format(n["children"])
                if n["tag"] == "h3":
                    self.end_bold()
                self.push(" " * 4)
                self.newline()
                self.at_p_boundary = True
            elif n["tag"] in ["h5", "h6"]:
                self.start_p()
                self.start_bold()
                self._format(n["children"])
                self.end_bold()
                self.end_p()
            elif n["tag"] in ("html", "footnote-definition", "footnote-reference"):
                pass
            elif n["tag"] == "alert":
                level = n["level"]
                self.start_p()
                self.push("│ ")
                self.start_bold()
                self.text(level.title())
                self.end_bold()
                self.newline()
                self.at_p_boundary = True
                self._format(n["children"])
                self.pop("│ ")
            elif n["tag"] == "dl":
                self.start_p()
                self._format(n["children"])
                self.end_p()
            elif n["tag"] == "dt":
                self.newline()
                self.start_bold()
                self._format(n["children"])
                self.end_bold()
                self.newline()
                self.at_p_boundary = True
            elif n["tag"] == "dd":
                self.newline()
                self.push()
                self._format(n["children"])
                self.pop()
            else:
                self._format(n.get("children", []))

    def text(self, s):
        self.space_needed = self.space_needed or s.startswith(" ")
        for word in s.split():
            if self.column + len(word) + self.space_needed > self.width:
                self.newline()
            self.pr(word)
            self.space_needed = True
        self.space_needed = s.endswith(" ")

    def code_block(self, n):
        self.newline()
        # A code block should only contains text. Ignore everything else.
        sio = io.StringIO()

        def collect_text(n):
            if isinstance(n, str):
                sio.write(n)
            else:
                for c in n.get("children", []):
                    collect_text(c)

        collect_text(n)
        text = sio.getvalue()
        # Write each line with the prefix.
        # Strip whitespace at the end. It will only add superfluous newlines.
        # Whitespace at the start may be important, so keep it there.
        self.write_lines(text.rstrip())

    def write_lines(self, text):
        for line in text.split("\n"):
            self.pr(line)
            self.newline()

    def start_p(self):
        self.blank_line()

    def end_p(self):
        pass

    def blank_line(self):
        if self.at_p_boundary:
            return
        self.newlines(2)
        self.at_p_boundary = True

    def start_item(self):
        self.newline()
        self.pr("- ")
        self.push()
        self.at_p_boundary = True

    def end_item(self):
        self.pop()

    def start_quote(self):
        self.newline()
        self.push("> ")

    def end_quote(self):
        self.pop("> ")

    def start_bold(self):
        pass

    def end_bold(self):
        pass

    def start_italics(self):
        pass

    def end_italics(self):
        pass

    def pr(self, s, visible=True):
        if self.at_line_start:
            self.write(self.line_prefix)
        if self.space_needed:
            self.write(" ")
        self.write(s, visible)
        self.at_p_boundary = False
        self.at_line_start = False
        self.space_needed = False

    def write(self, s, visible=True):
        self.out.write(s)
        if visible:
            self.column += len(s)

    def newline(self):
        if not self.at_line_start:
            self.out.write("\n")
            self.column = 0
            self.at_line_start = True
            self.space_needed = False

    def newlines(self, count):
        assert count >= 1
        self.newline()
        for _ in range(count - 1):
            self.out.write("\n")

    def push(self, end="  "):
        self.line_prefix += end

    def pop(self, end="  "):
        assert self.line_prefix.endswith(end)
        self.line_prefix = self.line_prefix[: -len(end)]


class StructuredCLI(StructuredText):
    def __init__(self, out, width=None):
        import cli

        super().__init__(out, width=width or cli.terminal_width())

    def start_bold(self):
        self.pr("\033b>", visible=False)

    def end_bold(self):
        self.pr("\033/b>", visible=False)

    def start_italics(self):
        self.pr("\033i>", visible=False)

    def end_italics(self):
        self.pr("\033/i>", visible=False)


def upper_case(n):
    """Convert text to upper case.

    This does not convert text in code, pre, tables, and html, but in other
    elements."""
    if isinstance(n, str):
        return n.upper()
    elif n["tag"] in ["code", "pre", "table", "html"]:
        return n
    elif n["tag"] in ["list"]:
        new = n.copy()
        new["items"] = [upper_case(i) for i in n["items"]]
        return new
    else:
        children = n.get("children", None)
        new = n.copy()
        if children is not None:
            new["children"] = [upper_case(c) for c in children]
        return new
