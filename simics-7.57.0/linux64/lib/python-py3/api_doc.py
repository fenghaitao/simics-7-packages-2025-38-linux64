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

import json
import structured_text
import sys
import bz2
import conf
from pathlib import Path
from dataclasses import dataclass

import simicsutils.internal
import simicsutils.host


@dataclass
class Api:
    index = {}
    pages = []

    def add_api_json(self, api):
        # Maps page indexes in api to indexes in our page list
        page_map = {}
        for topic, i in api["index"].items():
            if topic in self.index:
                # Skip items that are already documented
                continue
            if i in page_map:
                self.index[topic] = page_map[i]
            else:
                page = api["pages"][i]
                page_id = len(self.pages)
                self.index[topic] = page_id
                page_map[i] = page_id
                self.pages.append(page)

    def topics(self):
        return self.index.keys()

    def print_doc(self, topic):
        if topic not in self.index:
            return False
        i = self.index[topic]
        page = self.pages[i]
        formatter = structured_text.StructuredCLI(sys.stdout)
        formatter.format(page["text"])
        return True

    def apropos(self, needle):
        needle = needle.lower()
        for page in self.pages:
            id = page["id"]
            text = page["text"]
            for s in page_text(text):
                if needle in s.lower():
                    yield id
                    break


_api_doc_data = None


def load_package_api_json(pkg_id, pkg_path):
    path = Path(pkg_path) / conf.sim.host_type / "doc" / f"{pkg_id}.api.json"
    bz_path = path.with_name(path.name + ".bz2")
    if bz_path.exists():
        with bz2.BZ2File(pkg_path, "rb") as f:
            return json.load(f)
    if path.exists():
        return json.load(path.open())
    return None


def package_info():
    """Return the package info.

    This is a separate function to allow us to test with a custom package list.
    """
    return [(pkg_id, pkg_path)
            for (_, pkg_id, _, _, _, _, _, _, _, pkg_path, *_)
             in conf.sim.package_info]


def load_api_doc():
    api = Api()
    # This should be in package priority order to get documentation from
    # the most prioritized package first
    for (pkg_id, pkg_path) in package_info():
        pkg_api = load_package_api_json(pkg_id, pkg_path)
        if pkg_api is not None:
            api.add_api_json(pkg_api)
    return api


def get_api_doc():
    global _api_doc_data
    if _api_doc_data is None:
        _api_doc_data = load_api_doc()
    return _api_doc_data


def page_text(text):
    for element in text:
        if isinstance(element, str):
            yield element
        elif element["tag"] in ["code", "pre"]:
            # pre and code has its text in code
            yield element.get("code", [])
        elif element["tag"] == "list":
            # lists have items with elements
            for item in element.get("items", []):
                yield from page_text(item)
        elif element["tag"] == "table":
            # tables have header and rows with elements
            for td in element.get("header", []):
                yield from page_text(td)
            for row in element.get("rows", []):
                for td in row:
                    yield from page_text(td)
        else:
            # other tags have children (if any) with elements
            yield from page_text(element.get("children", []))


def topics():
    """Return the list of API topics."""
    return get_api_doc().topics()


def print_doc(topic):
    """Print documentation for the given topic.

    Returns `True` if the topic exists."""
    return get_api_doc().print_doc(topic)


def apropos(needle):
    """Look for the `needle` in all the API pages.

    Yields the ids of all the matching pages."""
    yield from get_api_doc().apropos(needle)
