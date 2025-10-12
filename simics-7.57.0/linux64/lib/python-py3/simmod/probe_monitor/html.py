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

import os
import json

import cli

def html_esc(s):
    # Escape string for html output
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace("\n", "<br>")
    return s

html_start = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Performance Report</title>
    <script type="text/javascript" src="https://cdn.plot.ly/plotly-2.25.2.min.js" charset="utf-8" ></script>
  </head>
"""

html_css = """
  <STYLE>
    .myTable {
      width: 100%;
      text-align: left;
      background-color: #EDEDED;
      border-collapse: collapse;
    }
    .myTable th {
      background-color: Silver;
      color: black;
      text-align: center;
    }
    .myTable td,
    .myTable th {
      padding: 5px;
      border: 1px solid #EDEDED;
    }

    .lighttheme {
      background-color : White;
    }
    .darktheme {
      background-color : #EDEDED;
    }

    /* Styling for the accordion */
    .accordion {
        color: #444;
        cursor: pointer;
        padding: 10px;
        width: 100%;
        border: none;
        text-align: left;
        outline: none;
        font-size: 16px;
        transition: 0.4s;
      }
      .active {
        background-color: Turquoise;
      }
      .inactive {
        background-color: Aquamarine;
      }
      .accordion:hover {
        background-color: Cyan;
      }
      .panel {
        padding: 0 18px;
        display: block;
        background-color: white;
        overflow: hidden;
      }

      /* Styling for the tool-tip hover-over */
      .tooltip-icon {
          position: absolute;
          right: 20px; /* Position the icon to the far right */
          cursor: pointer;
      }
      .tooltip-content {
          display: none; /* Initially hide the tooltip */
          position: absolute;
          right: 0; /* Align the tooltip to the right edge of the button */
          top: 100%; /* Position the tooltip below the icon */
          background-color: #333;
          color: #fff;
          padding: 10px;
          border-radius: 5px;
          min-width: 500px; /* Minimum width for the tooltip */
          max-width: 800px; /* Maximum width for the tooltip */
          box-shadow: 0 0 5px rgba(0, 0, 0, 0.3);
          z-index: 10;
          white-space: normal; /* Allow text to wrap */
          text-align: left; /* Align text to the left */
      }
      .tooltip-content a {
         color: #1E90FF; /* Light blue color for links */
         text-decoration: underline; /* Underline for better visibility */
         transition: color 0.3s; /* Smooth transition for color change */
      }
      .tooltip-content a:hover {
         color: #FFD700; /* Gold color on hover for high contrast */
      }
      .tooltip-icon:hover .tooltip-content {
          display: block; /* Show the tooltip on hover */
      }

      hr {
         border: none;
         height: 1px;
         background-color: Black; /* Line-color!! */
         margin: 0;
      }
      .hr-container {
         background-color: Aquamarine;
      }
  </STYLE>
"""

body_start = """
  <body>
"""


html_end = """
  </body>
</html>
"""

script_end = """
      // Function to toggle the accordion on click
      function toggleAccordion() {
          var panel = this.nextElementSibling;
          if (panel.style.display == "none") { // Open it
              panel.style.display = "block";
              this.classList.remove("inactive");
              this.classList.add("active");
          } else { // Close it
              panel.style.display = "none";
              this.classList.remove("active");
              this.classList.add("inactive");
          }
      }

      // Add toggleAccordion for all accordion buttons
      const accordions = document.querySelectorAll(".accordion");
      const isIndexPage = window.location.pathname.endsWith("index.html");
      for (let i = 0; i < accordions.length; i++) {
          var panel = accordions[i].nextElementSibling;
          if (isIndexPage && i == 0) {
              accordions[i].classList.add("active");
              panel.style.display = "block";
          } else {
              accordions[i].classList.add("inactive");
              panel.style.display = "none";
          }
          accordions[i].addEventListener("click", toggleAccordion);
      }
"""

class HtmlPage:
    def __init__(self, html_dir=".", page_name="index.html",
                 main_page=False, test_mode=False):
        self.page_name = page_name
        self.filename = os.path.join(html_dir, page_name)
        self.link_name = page_name.replace(".html", '')
        self.main_page = main_page
        self.test_mode = test_mode
        self.heading = ""
        self.html = ""
        self.script = ""
        self.resize_divs = []
        self.owner_divs = {}  # {owner : [divs]}

    def html_reference(self, link_name=None):
        return (f'<a href="{self.page_name}">'
                f'{link_name if link_name else self.link_name}</a>')

    def add_owner_divs(self, d):
        for k, v in d.items():
            self.owner_divs.setdefault(k, [])
            self.owner_divs[k].extend(v)

    def add_section(self, html, js, resize_divs):
        self.html += html
        self.script += js
        self.resize_divs += resize_divs

    def add_separator(self):
        self.add_html('<div class="hr-container"><hr></div>')

    def add_html(self, html):
        self.html += html

    def add_heading(self, html):
        self.heading += html

    def add_js(self, js):
        self.script += js

    def start_section(self, button_name, tooltip=""):
        self.add_accordion(button_name, tooltip)
        self.html += '<DIV class="panel">\n'

    def end_section(self):
        self.html += '</DIV>\n'

    def add_accordion(self, button_name, tooltip=""):
        tt = ""
        if tooltip:
            tt = ('<span class="tooltip-icon">ℹ️'
                  f'<div class="tooltip-content">{tooltip}</div></span>')
        self.html += f'<button class="accordion">{button_name}{tt}</button>'

    def add_svg(self, svg_filename, height):
        self.html += f"""
        <object class="panel" data="{svg_filename}" type="image/svg+xml" width=1200 height={height}>
        <img src="fan.png" width=1200 height={height} />
        </object>"""

    def add_radio_buttons(self):
        if not self.owner_divs:
            return

        # Html code at the top of the page
        t = '<div class="radio-group"><b>Plot filters</b>:'
        for o in sorted(self.owner_divs):
            owner = html_esc(o)
            t += '<label>'
            t += f'<input type="checkbox" id="{owner}" checked>{owner}'
            t += '</label>'
        t += '</div>'
        self.heading += t

        # Java-script that handled when the checkboxes are pressed.
        js = f"const ownerPlots = {json.dumps(self.owner_divs)};"
        js += """
        // Function to toggle visibility of plots based on checkbox state
        function togglePlots(ownerId, isVisible) {
            const plotIds = ownerPlots[ownerId];
            plotIds.forEach(plotId => {
                const plotElement = document.getElementById(plotId);
                if (plotElement) {
                    plotElement.style.display = isVisible ? 'block' : 'none';
                }
           });
        }

        // Attach event listeners to checkboxes and initialize visibility
        Object.keys(ownerPlots).forEach(ownerId => {
            const checkbox = document.getElementById(ownerId);
            checkbox.addEventListener('change', function() {
                togglePlots(ownerId, this.checked);
            });
            // Initialize visibility based on default checkbox state
            togglePlots(ownerId, checkbox.checked);
        });"""
        self.script += js

    # Add javascript code that handles window resizes so the plots
    # fills up the width of the browser
    def add_resize_js(self):
        divs = ",".join([f"'{d}'" for d in self.resize_divs])
        js = """
        // Avoid window-resize to happen many times
        function debounce(func, wait) {
            let timeout;
            return function(...args) {
                const later = () => {
                    timeout = null;
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }"""
        js += f"""
        function handleResize() {{
            const w = window.innerWidth * 0.95;
            const divIds = [{divs}];
            divIds.forEach(divId => {{
                Plotly.relayout(divId, {{width: w}});
            }});
        }};
        window.onresize = debounce(handleResize, 100);
        """
        self.script += js

    def finalize(self):
        self.add_radio_buttons()

        self.add_resize_js()
        self.script += script_end

        # Put together the entire file contents
        contents = html_start
        contents += html_css
        contents += body_start
        contents += self.heading
        contents += self.html
        contents += f"<script>\n{self.script}\n</script>"
        contents += html_end

        # For unit-test, allow test-mode to just return the generated
        # html.
        if self.test_mode:
            return contents

        # Write the result to the file
        try:
            fd = open(self.filename, "w+b")
        except OSError as msg:
            raise cli.CliError(f"Error:{msg}")

        blob = bytearray(contents, encoding="utf-8")
        fd.write(blob)
        fd.close()

class HtmlKeyValueTable:
    def __init__(self, html_page):
        self.html_page = html_page
        self.cssclass = "lighttheme"
        self.html = """
        <DIV class="panel">
        <TABLE class="myTable">
          <TBODY>
        """

    def _switch_ccsclass(self):
        if self.cssclass == "darktheme":
            self.cssclass = "lighttheme"
        elif self.cssclass == "lighttheme":
            self.cssclass = "darktheme"
        else:
            assert 0

    @staticmethod
    def _inner_table(lst):
        html = "<TABLE><TBODY>"
        for row in lst:
            html += "<TR>"
            for c in row:
                html += f"<TD>{c}</TD>\n"
            html += "</TR>"
        html += "</TBODY></TABLE>\n"
        return html


    @staticmethod
    def _is_matrix(v):
        if not isinstance(v, list):
            return False
        if not all([isinstance(e, list) for e in v]):
            return False
        return True

    def add_row(self, key, value):
        self._switch_ccsclass()
        if self._is_matrix(value):
            v = self._inner_table(value)
        else:
            v = value
        self.html += f"""
            <tr class={self.cssclass}>
              <td>{key}</td>
              <td>{v}</td>
            </tr>
        """

    def finalize(self):
        self.html += "</TBODY></TABLE></DIV>\n"
        self.html_page.add_html(self.html)

class HtmlGlobalProbeTable:
    def __init__(self, html_page):
        self.html_page = html_page
        self.cssclass = "lighttheme"
        self.html = """
        <DIV class="panel">
        <TABLE class="myTable">
          <THEAD>
            <TR>
              <TH>Probe Name</TH>
              <TH>Display Name</TH>
              <TH>Value</th>
              <TH>Formatted Value</TH>
            </TR>
          </THEAD>
        <TBODY>
        """
    def _switch_ccsclass(self):
        if self.cssclass == "darktheme":
            self.cssclass = "lighttheme"
        elif self.cssclass == "lighttheme":
            self.cssclass = "darktheme"
        else:
            assert 0

    def add_global_probe_result(self, probe_name, display_name, value,
                                formatted_value):
        self._switch_ccsclass()
        self.html += f"""
            <tr class={self.cssclass}>
              <td>{probe_name}</td>
              <td>{display_name}</td>
              <td align="right">{value}</td>
              <td align="right">{formatted_value}</td>
            </tr>
        """

    def finalize(self):
        self.html += "</TBODY></TABLE></DIV>\n"
        self.html_page.add_html(self.html)

class HtmlObjectProbeTable:
    def __init__(self, html_page):
        self.html_page = html_page
        self.cssclass = "lighttheme"
        self.html = """
        <DIV class="panel">
        <TABLE class="myTable">
          <THEAD>
            <TR>
              <TH>Probe Name</TH>
              <TH>Display Name</TH>
              <TH>Object</TH>
              <TH>Value</th>
              <TH>Formatted Value</TH>
            </TR>
          </THEAD>
        <TBODY>
        """
    def _switch_ccsclass(self):
        if self.cssclass == "darktheme":
            self.cssclass = "lighttheme"
        elif self.cssclass == "lighttheme":
            self.cssclass = "darktheme"
        else:
            assert 0

    def add_object_probe_results(self, probe_name, display_name,
                                 object_value_list):
        self._switch_ccsclass()
        num = len(object_value_list)
        (o, v, f) = object_value_list[0]
        self.html += f"""
          <tr class={self.cssclass}>
            <td rowspan="{num}">{probe_name}</td>
            <td rowspan="{num}">{display_name}</td>
            <td>{o}</td>
            <td align="right">{v}</td>
            <td align="right">{f}</td>
          </tr>"""

        self.html += "".join([
            f"""<tr class={self.cssclass}>
            <td>{o}</td>
            <td align="right">{v}</td>
            <td align="right">{f}</td>
            </tr>""" for (o, v, f) in object_value_list[1:]])

    def finalize(self):
        self.html += "</TBODY></TABLE></DIV>\n"
        self.html_page.add_html(self.html)
