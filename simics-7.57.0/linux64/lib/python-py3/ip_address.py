# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import cli, re
import unittest

def check_ip_addr(tgt_ip):
    "Check validity of an IP address. Raise CliError on failure."
    if not tgt_ip:
        raise cli.CliError("Malformed IP address '%s'" % tgt_ip)
    if re.match(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$", tgt_ip):
        return "IPv4"
    s = tgt_ip.split('::')
    dc = len(s)
    if dc > 2:
        raise cli.CliError("Malformed IP address '%s'" % tgt_ip)
    if dc == 2:
        if s[0] != '':
            lh = s[0].split(':')
        else:
            lh = []
        if s[1] != '':
            rh = s[1].split(':')
        else:
            rh = []
        if len(lh) + len(rh) >= 8:
            raise cli.CliError("Malformed IP address '%s'" % tgt_ip)
        l = lh + rh
    else:
        l = s[0].split(':')
        if len(l) != 8:
            raise cli.CliError("Malformed IP address '%s'" % tgt_ip)
    for x in l:
        if not re.match("[0-9a-fA-F]{1,4}$", x):
            raise cli.CliError("Malformed IP address '%s'" % tgt_ip)
    return "IPv6"

class Test_check_ip_addr(unittest.TestCase):
    def test_valid_ipv4_1(self):
        self.assertEqual(check_ip_addr("1.2.3.4"), "IPv4")
    def test_valid_ipv4_2(self):
        self.assertEqual(check_ip_addr("0.0.0.0"), "IPv4")  # nosec
    def test_valid_ipv4_3(self):
        self.assertEqual(check_ip_addr("255.255.255.255"), "IPv4")

    def test_valid_ipv6_1(self):
        self.assertEqual(check_ip_addr("::"), "IPv6")
    def test_valid_ipv6_2(self):
        self.assertEqual(check_ip_addr("0::0"), "IPv6")
    def test_valid_ipv6_3(self):
        self.assertEqual(check_ip_addr("01:02::03:04"), "IPv6")
    def test_valid_ipv6_4(self):
        self.assertEqual(check_ip_addr("::1"), "IPv6")
    def test_valid_ipv6_5(self):
        self.assertEqual(check_ip_addr("1::"), "IPv6")
    def test_valid_ipv6_6(self):
        self.assertEqual(
            check_ip_addr("0000:aaaa:2222:DDDD:4444:555:6666:7777"), "IPv6")

    def test_invalid_1(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1")
    def test_invalid_2(self):
        # This is actually a valid IPv4 address according to the normal
        # rules (a shorthand for 1.0.0.2)
        self.assertRaises(cli.CliError, check_ip_addr, "1.2")
    def test_invalid_3(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2.3")
    def test_invalid_4(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2.3.4.5")
    def test_invalid_5(self):
        self.assertRaises(cli.CliError, check_ip_addr, " 1.2.3.4")
    def test_invalid_6(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2.3.4 ")
    def test_invalid_7(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2.a.4")
    def test_invalid_8(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2..4")
    def test_invalid_9(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1.2..3.4")
    def test_invalid_10(self):
        self.assertRaises(cli.CliError, check_ip_addr, "")
    def test_invalid_11(self):
        self.assertRaises(cli.CliError, check_ip_addr, ":")
    def test_invalid_12(self):
        self.assertRaises(cli.CliError, check_ip_addr, ":::")
    def test_invalid_13(self):
        self.assertRaises(cli.CliError, check_ip_addr, ":::0")
    def test_invalid_14(self):
        self.assertRaises(cli.CliError, check_ip_addr, ":1")
    def test_invalid_15(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1:")
    def test_invalid_16(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1g::")
    def test_invalid_17(self):
        self.assertRaises(cli.CliError, check_ip_addr, "00000::")
    def test_invalid_18(self):
        self.assertRaises(cli.CliError, check_ip_addr, "::00000")
    def test_invalid_19(self):
        self.assertRaises(cli.CliError, check_ip_addr, "1111::2222::3333")
    def test_invalid_20(self):
        self.assertRaises(cli.CliError, check_ip_addr,
                          "1111:2222:3333:4444:5555:6666:7777:8888:9999")
    def test_invalid_21(self):
        self.assertRaises(cli.CliError, check_ip_addr,
                          "1111:2222:3333:4444::5555:6666:7777:8888")

def ip_mask_shorthand(ip):
    """Split the IP address from the prefix length (netmask).

    If given a string of the form 'a.b.c.d/24', it returns
    ('a.b.c.d', 24), and if given a string without the '/x' suffix,
    return (ip, None). Also check that the IP address is valid."""
    ip = ip.split('/', 1)
    if len(ip) == 1:
        (ip, prefix_len) = (ip[0], None)
    else:
        (ip, n) = ip
        prefix_len = int(n)
    check_ip_addr(ip)
    return ip, prefix_len

def netmask_len(netmask):
    "Calculate the number of set bits in an IPv4-style netmask"
    bytes = [int(x) for x in netmask.split(".")]
    if len(bytes) != 4:
        raise Exception("wrong number of bytes")
    plen = 0
    while bytes and bytes[0] == 255:
        plen += 8
        del bytes[0]
    if not bytes:
        return plen

    if bytes[0] != 0:
        plen += 8
        x = ~bytes.pop(0) & 255
        while x & 1:
            plen -= 1
            x = x >> 1
        if x:
            raise Exception("malformed IP address.")

    for x in bytes:
        if x:
            raise Exception("malformed IP address")
    return plen

def ip_address_is_multicast(address):
    """Return true if it is a multicast address"""
    addr = address.split("/")[0]
    if check_ip_addr(addr) == "IPv6":
        return (addr[0:2].upper() == "FF"
                or addr[0:3].upper() == "255")
    else:
        return addr[0:3] == "224"
