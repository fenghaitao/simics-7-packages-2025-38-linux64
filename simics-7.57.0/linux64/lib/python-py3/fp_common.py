#!/usr/bin/env python

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


def py3_cmp(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return all((t[0] == t[1]) for t in zip(a, b))
    return ((a > b) - (a < b))

# Implementation of IEEE floating point for test purposes

# Use an intermediate representation of FP values of arbitrary precision:
#
# A triplet (s, e, m) of integers (s = 0 or 1, m >= 0), representing:
#  (-1)**s * 2**e * m   if e != inf_exp
#  (-1)**s * Inf        if e == inf_exp and m != 0
#
# Note that this is not a unique representation.
# NaN is represented by None (almost homophones!)

inf_exp = 9999999

# return floor(log2(x)), or -1 if x==0
def ilog2(x):
    return x.bit_length() - 1

def unit_test_ilog2():
    assert ilog2(0) == -1
    assert ilog2(1) == 0
    assert ilog2(32) == 5
    assert ilog2(15) == 3
    assert ilog2(1 << 80) == 80

def shl(x, n):
    if n >= 0:
        return x << n
    else:
        return x >> -n

def shr(x, n):
    if n >= 0:
        return x >> n
    else:
        return x << -n

# rounding result flags
FP_incr      = 1 << 0         # fraction was incremented when rounding
FP_loss      = 1 << 1         # bit (precision) loss occurred when rounding
FP_tiny      = 1 << 2         # result was tiny before rounding
FP_overflow  = 1 << 3         # rounded result exceeds exponential range
FP_underflow = 1 << 4         # underflow occurred

# exception enable flags: these affect the result generated from rounding
FP_enable_underflow = 1 << 0
FP_enable_overflow  = 1 << 1

# rounding modes
class Rounding_mode:
    def __init__(self, round, overflow):
        self.round = round
        self.overflow = overflow

FP_round_nearest = Rounding_mode(lambda sign, last_drop, rest_drop, last_pos:
                                 last_drop and (rest_drop or last_pos),
                                 [1, 1])
FP_round_zero = Rounding_mode(lambda sign, last_drop, rest_drop, last_pos: 0,
                              [0, 0])
FP_round_pinf = Rounding_mode(lambda sign, last_drop, rest_drop, last_pos:
                              (not sign) and (last_drop or rest_drop),
                              [1, 0])
FP_round_ninf = Rounding_mode(lambda sign, last_drop, rest_drop, last_pos:
                              sign and (last_drop or rest_drop),
                              [0, 1])

# Round an intermediate number to an integer, returning (result, flags)
# where the result is also an intermediate number (thus there is no overflow)
def interm_round_to_int(data, rmode):
    (s, e, m) = data
    flags = 0
    if e < 0:
        # will have to shift out bits - may cause loss of precision
        mm = m >> -e
        last_pos = mm & 1
        last_dropped = (m >> (-e - 1)) & 1
        rest_dropped = (m & ((1 << (-e - 1)) - 1)) != 0
        if last_dropped or rest_dropped:
            flags |= FP_loss
        if rmode.round(s, last_dropped, rest_dropped, last_pos):
            # rounding causing increment of mantissa
            flags |= FP_incr
            mm += 1
        res = (s, 0, mm)
    else:
        res = (s, e, m)
    return (res, flags)

def unit_test_interm_round_to_int():
    def expect_round(val, rm, expected_res, expected_fl):
        (r, fl) = interm_round_to_int(val, rm)
        assert interm_eq(r, expected_res)
        assert fl == expected_fl

    # try numbers that are already integral
    for x in [(0, 0, 0), (1, 0, 1), (0, 5678, 1234)]:
        for rm in [FP_round_nearest, FP_round_ninf, FP_round_pinf,
                   FP_round_zero]:
            expect_round(x, rm, x, 0)

    expect_round((0, -4, 0x18), FP_round_nearest, (0, 0, 2), FP_loss | FP_incr)
    expect_round((1, -100, 1), FP_round_ninf, (1, 0, 1), FP_loss | FP_incr)
    expect_round((1, -100, 1), FP_round_pinf, (1, 0, 0), FP_loss)
    expect_round((0, -100, 1), FP_round_ninf, (0, 0, 0), FP_loss)
    expect_round((0, -100, 1), FP_round_pinf, (0, 0, 1), FP_loss | FP_incr)

    expect_round((0, inf_exp, 1), FP_round_nearest, (0, inf_exp, 1), 0)

class FP_repr:
    def __init__(self, exp_width, frac_width, gen_qnan):
        self.exp_width = exp_width
        self.frac_width = frac_width
        self.max_exp = (1 << exp_width) - 1
        self.max_frac = (1 << frac_width) - 1
        self.exp_bias = (1 << (self.exp_width - 1)) - 1
        self.gen_qnan = gen_qnan

    def unpack(self, x):
        s = x >> (self.exp_width + self.frac_width)
        e = (x >> self.frac_width) & self.max_exp
        f = x & self.max_frac
        return (s, e, f)

    # Convert a packed number to intermediate representation.
    # Does not handle NaNs.
    def fp_to_interm(self, x):
        (s, e, f) = self.unpack(x)

        if e == self.max_exp:
            return (s, inf_exp, 1)      # infinity
        if e > 0:
            # normal number
            return (s, e - self.exp_bias - self.frac_width,
                    f | 1 << self.frac_width)
        else:
            # subnormal number or zero
            return (s, e - self.exp_bias - self.frac_width + 1, f)

    def pack(self, sign, exp, frac):
        return (sign << (self.exp_width + self.frac_width)
                | exp << self.frac_width | frac)

    # Round and pack an intermediate number to its packed representation
    # with a given rounding mode (FP_round_* above) and enabled exceptions.
    # Return (packed, flags) where flags are the FP_ rounding flags above
    def interm_to_fp(self, x, rmode, enable=0):
        if x == None:
            return (self.gen_qnan, 0)
        (s, e, m) = x
        if m == 0:
            # exact zero result
            return (self.pack(s, 0, 0), 0)
        if e == inf_exp:
            # exact infinite result
            return (self.pack(s, self.max_exp, 0), 0)
        flags = 0
        b = ilog2(m) + 1                # bits needed for fraction
        ex = e + b + self.exp_bias - 1  # packed exponent
        sh = b - (self.frac_width + 1)  # how much to shift m to the right
        if ex <= 0:
            # tiny result: too small for normal exponent range
            flags |= FP_tiny
            if enable & FP_enable_underflow:
                # scale up result by bias
                ex += 3 * (1 << (self.exp_width - 2))
                assert ex > 0           # must be enough to normalise
                flags |= FP_underflow
            else:
                # denorm: shift out even more (and no more implicit leading 1)
                sh += -ex + 1
        if sh > 0:
            # must shift out bits to the right
            mm = m >> sh                # resulting mantissa
            last_pos = mm & 1
            last_dropped = (m >> (sh - 1)) & 1
            rest_dropped = (m & ((1 << (sh - 1)) - 1)) != 0
            if last_dropped or rest_dropped:
                flags |= FP_loss
                if flags & FP_tiny:
                    flags |= FP_underflow
            if rmode.round(s, last_dropped, rest_dropped, last_pos):
                # rounding causing increment of mantissa
                flags |= FP_incr
                mm += 1
                if mm & (mm - 1) == 0:
                    # increment caused mantissa to need one more bit
                    if ex >= 0:
                        if ex > 0:
                            # For normal numbers, lose another digit
                            # (always a 0). If it's a denorm, we always have
                            # room for one more digit.
                            mm >>= 1
                        # renormalise
                        ex += 1
        else:
            # no bits shifted out
            mm = m << -sh
        if ex >= self.max_exp:
            flags |= FP_overflow
            if enable & FP_enable_overflow:
                # return result scaled down by bias
                adjusted_ex = ex - 3 * (1 << (self.exp_width - 2))
                assert adjusted_ex <= self.max_exp
                return (self.pack(s, adjusted_ex, mm & self.max_frac), flags)
            else:
                # result depends on rounding mode
                if rmode.overflow[s]:
                    # round result to infinity
                    return (self.pack(s, self.max_exp, 0), flags | FP_loss)
                else:
                    # round result to largest finite number
                    return (self.pack(s, self.max_exp - 1, self.max_frac),
                            flags | FP_loss)
        if ex > 0:
            # normal
            return (self.pack(s, ex, mm & self.max_frac), flags)
        else:
            # denorm
            return (self.pack(s, 0, mm), flags)

# Convert an integer to intermediate representation.
def int_to_interm(x):
    return (x < 0, 0, abs(x))

# Round an intermediate number to an integer in [int_min, int_max].
# Return (result, flags) where flags are the FP_ rounding flags above,
# where result is int_min/int_max on overflow.
def interm_to_int(data, int_min, int_max, rmode, enable=0):
    (s, e, m) = data
    if e == inf_exp:
        return ((int_max, int_min)[s], FP_overflow | FP_loss)
    ((s2, e2, m2), flags) = interm_round_to_int((s, e, m), rmode)
    mm = m2 << e2
    res = mm * (1 - s * 2)
    if res > int_max:
        res = int_max
        flags |= FP_overflow | FP_loss
    elif res < int_min:
        res = int_min
        flags |= FP_overflow | FP_loss
    return (res, flags)

# test equality of two intermediate numbers
def interm_eq(left, right):
    (sa, ea, ma) = left
    (sb, eb, mb) = right
    e = min(ea, eb)
    return sa == sb and ma << (ea - e) == mb << (eb - e)

def unit_test_interm_eq():
    assert interm_eq((1, 8, 9), (1, 6, 36))
    assert interm_eq((0, -71, 80), (0, -67, 5))

def unit_test_fp_to_interm():
    fp32 = FP_repr(8, 23, 0x7fc00000)
    assert interm_eq(fp32.fp_to_interm(0x3f800000), (0, 0, 1))
    assert interm_eq(fp32.fp_to_interm(0xbf800000), (1, 0, 1))
    assert interm_eq(fp32.fp_to_interm(0x3f400000), (0, -2, 3))
    assert interm_eq(fp32.fp_to_interm(0x00000001), (0, -149, 1))
    assert interm_eq(fp32.fp_to_interm(0x80001000), (1, -137, 1))
    assert fp32.fp_to_interm(0x7f800000) == (0, inf_exp, 1)

def unit_test_interm_to_fp():
    fp32 = FP_repr(8, 23, 0x7fc00000)

    # lossless transformations
    for p in [0x3f800000, 0x7f7fffff, 0x80800000, 0xc593cda1]:
        assert (fp32.interm_to_fp(fp32.fp_to_interm(p), FP_round_nearest)
                == (p, 0))
    for p in [0x00000001,  0x00016a57]:
        assert (fp32.interm_to_fp(fp32.fp_to_interm(p), FP_round_nearest)
                == (p, FP_tiny))

    # underflowing results
    assert (fp32.interm_to_fp((0, -155, 0x7fffff), FP_round_zero)
            == (0x0001ffff, FP_loss | FP_tiny | FP_underflow))
    assert (fp32.interm_to_fp((0, -155, 0x7fffff), FP_round_nearest)
            == (0x00020000, FP_loss | FP_incr | FP_tiny | FP_underflow))
    assert (fp32.interm_to_fp((0, -150, 0xffffff), FP_round_pinf)
            == (0x00800000, FP_loss | FP_incr | FP_tiny | FP_underflow))
    assert (fp32.interm_to_fp((0, -149, 0x7ec), FP_round_zero,
                              FP_enable_underflow)
            == (0x5a7d8000, FP_tiny | FP_underflow))
    assert (fp32.interm_to_fp((0, -149, 0x7ec), FP_round_zero)
            == (0x000007ec, FP_tiny))

    # overflowing results
    assert (fp32.interm_to_fp((0, 150, 1), FP_round_nearest)
            == (0x7f800000, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((1, 150, 1), FP_round_nearest)
            == (0xff800000, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((0, 150, 1), FP_round_zero)
            == (0x7f7fffff, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((1, 150, 1), FP_round_zero)
            == (0xff7fffff, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((0, 150, 1), FP_round_pinf)
            == (0x7f800000, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((1, 150, 1), FP_round_pinf)
            == (0xff7fffff, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((0, 150, 1), FP_round_ninf)
            == (0x7f7fffff, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((1, 150, 1), FP_round_ninf)
            == (0xff800000, FP_overflow | FP_loss))
    assert (fp32.interm_to_fp((0, 150, 1), FP_round_pinf, FP_enable_overflow)
            == (0x2a800000, FP_overflow))

def unit_test_interm_to_int():

    for x in [0, 1, -1, 2394823, -329498, 0x7fffffff, -0x80000000]:
        assert (interm_to_int((x < 0, 0, abs(x)),
                              -(1 << 31), (1 << 31) - 1,
                              FP_round_nearest)
                == (x, 0))
    assert (interm_to_int((0, -4, 0x18), -(1 << 31), (1 << 31) - 1,
                          FP_round_nearest)
            == (2, FP_loss | FP_incr))
    assert (interm_to_int((0, 129, 1),  -(1 << 31), (1 << 31) - 1,
                          FP_round_nearest)
            == ((1 << 31) - 1, FP_overflow | FP_loss))
    assert (interm_to_int((1, 129, 1),  -(1 << 31), (1 << 31) - 1,
                          FP_round_nearest)
            == (-(1 << 31), FP_overflow | FP_loss))
    assert (interm_to_int((1, -100, 1), -(1 << 31), (1 << 31) - 1,
                          FP_round_ninf)
            == (-1, FP_loss | FP_incr))
    assert (interm_to_int((0, inf_exp, 1), 0, 1,
                          FP_round_zero)
            == (1, FP_loss | FP_overflow))
    assert (interm_to_int((1, inf_exp, 1), 0, 1,
                          FP_round_zero)
            == (0, FP_loss | FP_overflow))

# Multiply two intermediate numbers
def fpim_mul(left, right):
    (sa, ea, ma) = left
    (sb, eb, mb) = right
    if ea == inf_exp:
        if mb == 0:
            return None                 # Inf * 0 -> NaN
        return (sa ^ sb, inf_exp, 1)    # Inf * x -> Inf
    elif eb == inf_exp:
        if ma == 0:
            return None                 # 0 * Inf -> NaN
        return (sa ^ sb, inf_exp, 1)    # x * Inf -> Inf
    return (sa ^ sb, ea + eb, ma * mb)

def unit_test_fpim_mul():
    assert interm_eq(fpim_mul((1, 1, 3), (0, 5, 10)), (1, 0, 6 * 320))

# Add two intermediate numbers
def fpim_add(left, right, rmode):
    (sa, ea, ma) = left
    (sb, eb, mb) = right
    if ea == inf_exp:
        if eb == inf_exp and sa != sb:
            return None                 # +=Inf + -+Inf -> QNaN
        return (sa, inf_exp, 1)
    if eb == inf_exp:
        return (sb, inf_exp, 1)
    # shift to common exponent
    d = ea - eb
    if d > 0:
        ma <<= d
        ea -= d
    else:
        mb <<= -d
        eb -= -d
    if sa == sb:
        return (sa, ea, ma + mb)        # addition
    else:
        m = ma - mb                     # subtraction
        if m == 0:
            # ieee754 6.3: x - x == +0 unless rounding toward -Inf, in which
            # case it's -0
            return (rmode == FP_round_ninf, 0, 0)
        elif m > 0:
            return (sa, ea, m)
        else:
            return (sb, ea, -m)

def unit_test_fpim_add():
    assert interm_eq(fpim_add((1, 1, 3), (0, 5, 10), FP_round_nearest),
                     (0, 0, 314))
    assert interm_eq(fpim_add((0, -1, 3), (0, 1, 1), FP_round_nearest),
                     (0, -1, 7))
    assert fpim_add((1, 0, 0), (1, 0, 0), FP_round_nearest) == (1, 0, 0)

def fpim_sub(a, b, rmode):
    return fpim_add(a, fpim_neg(b), rmode)

def unit_test_fpim_sub():
    assert (fpim_sub((0, -38, 239), (0, -38, 239), FP_round_nearest)
            == (0, 0, 0))
    assert (fpim_sub((0, -38, 239), (0, -38, 239), FP_round_ninf)
            == (1, 0, 0))

def fpim_neg(x):
    if x == None:
        return x
    (s, e, m) = x
    return (s ^ 1, e, m)

def unit_test_fpim_neg():
    assert fpim_neg((0, 17, 234)) == (1, 17, 234)

# return one of {< = > ?}. a and b may be None (meaning NaN).
def fpim_cmp(a, b):
    if a == None or b == None:
        return '?'
    (sa, ea, ma) = a
    (sb, eb, mb) = b
    if sa != sb:
        if ma == 0 and mb == 0:
            return '='                  # -0 == +0
        else:
            return "><"[sa]
    else:
        # same sign
        emin = min(ea, eb)
        inv = 1 - (sa * 2)
        return "<=>"[py3_cmp(ma << (ea - emin), mb << (eb - emin)) * inv + 1]

def unit_test_fpim_cmp():
    assert fpim_cmp(None, None) == '?'
    assert fpim_cmp(None, (0, 17, 83)) == '?'
    assert fpim_cmp((0, 0, 0), (1, 0, 0)) == '='
    assert fpim_cmp((1, 2, 3), (0, 2, 3)) == '<'
    assert fpim_cmp((0, 17, 1), (0, 13, 16)) == '='
    assert fpim_cmp((0, 0, 2), (0, 0, 1)) == '>'
    assert fpim_cmp((1, 19, 1), (1, -17, 2039433)) == '<'

# Divide two numbers, using fbits fractional bits in the result
def fpim_div(left, right, fbits):
    (sa, ea, ma) = left
    (sb, eb, mb) = right
    if mb == 0:
        if ma == 0:
            return None                 # 0 / 0 -> NaN
        else:
            return (sa ^ sb, inf_exp, 1) # x / 0 -> Inf
    elif ea == inf_exp:
        if eb == inf_exp:
            return None                 # Inf / Inf -> NaN
        else:
            return (sa ^ sb, inf_exp, 1) # Inf / x -> Inf
    elif eb == inf_exp:
        return (sa ^ sb, 0, 0)          # x / Inf -> 0
    else:
        scale = fbits + ilog2(mb) - ilog2(ma) + 1
        (q, r) = divmod(ma << scale, mb)
        # Add an extra ghost bit if more bits were lost, so rounding behaves
        # correctly
        return (sa ^ sb, ea - eb - scale - 1, (q << 1) | (r != 0))

def unit_test_fpim_div():
    assert interm_eq(fpim_div((0, 0, 13), (1, -2, 1), 10), (1, 0, 52))
    (s, e, m) = fpim_div((0, 0, 1), (0, 1, 5), 20) # 1 / 10
    assert s == 0 and shl(m, e) == 0 and shl(m, e + 16) == 0x1999
    assert fpim_div((1, -13, 29), (1, inf_exp, 1), 80) == (0, 0, 0)
    assert fpim_div((1, -13, 29), (1, 0, 0), 80) == (0, inf_exp, 1)
    (s, e, m) = fpim_div((0, 0, 1), (0, 0, 0x1fffffffffffff), 55)
    assert s == 0 and shl(m, e + 106) == 0x20000000000001
    # make sure we get extra bits so the result rounds correctly
    (s, e, m) = fpim_div((0, 0, 0x10000001), (0, 0, 0x10000000), 8)
    assert s == 0 and shl(m, e + 8) == 0x100 and m > (1 << -e)

def isqrt(x):
    if x < 0:
        raise ValueError("isqrt on negative number")
    if x == 0:
        return 0
    t0 = x                              # lame starting guess
    while True:
        t1 = (t0 + x // t0) >> 1
        # iterate until no longer strictly decreasing
        if t1 >= t0:
            return t0
        t0 = t1

def unit_test_isqrt():
    assert isqrt(0) == 0
    for i in range(1, 100):
        assert isqrt(i * i) == i
        assert isqrt((i + 1) * (i + 1) - 1) == i
    for i in range(1, 100):
        assert isqrt(1 << (2 * i)) == 1 << i
        assert isqrt((1 << (2 * i)) - 1) < (1 << i)
    for i in range(1, 10000, 117):
        assert isqrt(i * i) == i
        assert isqrt(i * i - 1) == (i - 1)
    try:
        isqrt(-1)
    except ValueError:
        pass
    else:
        assert 0, "Square root on negative error does not raise exception"

# Calculate the square root of a number to at least fbits bits of precision
def fpim_sqrt(data, fbits):
    (s, e, m) = data
    if m == 0:
        return (s, 0, 0)               # sqrt(-0) = -0 according to ieee754
    elif s:
        return None
    elif e == inf_exp:
        return (0, inf_exp, 1)
    else:
        scale = fbits << 1
        (e, m) = (e - scale, m << scale)
        # make exponent even
        if e & 1:
            (e, m) = (e - 1, m << 1)
        (re, rm) = (e >> 1, isqrt(m))
        return (0, re - 1, rm << 1 | (rm * rm != m))

def unit_test_fpim_sqrt():
    assert fpim_sqrt((0, 0, 0), 17) == (0, 0, 0)
    for i in range(1, 100):
        assert interm_eq(fpim_sqrt((0, 0, i * i), 35), (0, 0, i))
        (s, e, m) = fpim_sqrt((0, 0, i * i - 1), 35)
        assert s == 0 and shl(m, e) == i - 1
        (s, e, m) = fpim_sqrt((0, 0, i * i + 1), 35)
        assert s == 0 and shl(m, e) == i
        assert interm_eq(fpim_sqrt((0, -28, i * i), 31), (0, -14, i))
    for i in range(1, 108731, 1319):
        assert interm_eq(fpim_sqrt((0, -14, i * i), 69), (0, -7, i))
    (s, e, m) = fpim_sqrt((0, 1, 1), 16) # sqrt(2)
    assert s == 0 and shl(m, e + 16) == 0x16a09

# Absolute value of an intermediate number
def fpim_abs(data):
    (s, e, m) = data
    return (0, e, m)

def unit_test_fpim_abs():
    assert fpim_abs((1, 4711, 1500)) == (0, 4711, 1500)

def unit_tests():
    for g in globals():
        if g.startswith('unit_test_'):
            globals()[g]()

if __name__ == "__main__":
    unit_tests()
