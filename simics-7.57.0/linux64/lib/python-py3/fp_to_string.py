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


# fp_to_string
#
# Floating point to string functions
#
# Available modes are "h" - 16-bit, "s" - 32-bit, "d" - 64-bit,
#                     "ed" - 80-bit, and "q" - 128-bit

# Data for fp_to_string
mode_data = {
    #       data  exp.  man.  imp.
    #       size  size  size   one
    "h"  : ( 16,   5,  10,   1),
    "s"  : ( 32,   8,  23,   1),
    "d"  : ( 64,  11,  52,   1),
    "ed" : ( 80,  15,  64,   0),
    "q"  : (128,  15, 112,   1)
    }

def fp_conv_common(mode, binary):
    (size, exp_size, man_size, imp_one) = mode_data[mode]
    unbiased_exp = ((binary >> man_size) & ((1 << exp_size) - 1))
    exp =  unbiased_exp - ((1 << (exp_size - 1)) - 1)
    if unbiased_exp == 0 and imp_one:
        # subnormal, add one to the exponent
        exp = exp + 1
    man = (binary & ((1 << man_size) - 1))
    if ((binary >> man_size) & ((1 << exp_size) - 1)):
        man |= (imp_one << man_size)
    sign = (binary >> (size - 1)) & 1

    # Check for NaNs
    nan = None
    if ((binary >> man_size) & ((1 << exp_size) - 1)) == ((1 << exp_size) - 1):
        if (binary >> (man_size - 1)) & 1:
            nan = "QNaN"
        else:
            if binary & ((1 << man_size) - 1):
                nan = "SNaN"
            else:
                if sign:
                    nan = "-Inf"
                else:
                    nan = "+Inf"
    return (size, exp_size, man_size, imp_one, exp, man, sign, nan)

def fp_to_binstring(mode, binary):
    binary = int(binary)
    (size, exp_size, man_size, imp_one, exp, man, sign, nan) = fp_conv_common(mode, binary)
    if nan != None:
        return nan

    if sign:
        ret = "-"
    else:
        ret = "+"

    if man & (1 << man_size):
        ret = ret + "1."
    else:
        ret = ret + "0."

    for c in range(man_size-1, -1, -1):
        if man & (1 << c):
            ret = ret + "1"
        else:
            ret = ret + "0"

    ret = ret + " * 2^(%d)" % (exp)

    return ret


# Converts the binary representation of floating point values to strings with num_digits precision.
def fp_to_string(mode, binary, num_digits):
    # Get all the needed data
    binary = int(binary)
    num_digits = int(num_digits)

    (size, exp_size, man_size, imp_one, exp, man, sign, nan) = fp_conv_common(mode, binary)

    if nan != None:
        return nan

    # Set up the numerator and denominator
    if exp >= 0:
        numer = man << exp
        denom = 1 << (man_size - 1 + imp_one)
    else:
        numer = man
        denom = (1 << (man_size - 1 + imp_one)) << -exp

    # Calculate the exponent
    expon = 0
    if man != 0:
        adj1 = 10
        adj2 = 1
        while adj1 != 1:
            if denom // numer * 10 >= adj1:
                numer *= adj1
                expon -= adj2
                adj1 *= 10
                adj2 += 1
            else:
                adj1 //= 10
                adj2 -= 1
        adj1 = 10
        adj2 = 1
        while adj1 != 1:
            if numer // denom >= adj1:
                numer //= adj1
                expon += adj2
                adj1 *= 10
                adj2 += 1
            else:
                adj1 //= 10
                adj2 -= 1

    # Calculate the digits
    digits = []
    for i in range(0, num_digits):
        # Calculate the digit
        digits += [numer // denom]
        numer = (numer % denom) * 10

        # Round last digit
        if (i == num_digits - 1) and (numer // denom >= 5):
            j = num_digits - 1
            while True:
                digits[j] += 1
                if digits[j] == 10:
                    digits[j] = 0
                    if i == 0:
                        digits = [0] + digits
                        expon += 1
                    else:
                        j -= 1
                else:
                    break

    # Convert to string
    if sign:
        result = "-"
    else:
        result = " "
    result += "%i." % digits[0]
    for digit in digits[1:]:
        result += "%i" % digit
    result += "e%+i" % expon

    return result


# Like fp_to_string, but pads the string with spaces to the specified width.
def fp_to_string_fixed(mode, binary, num_digits, width):
    result = fp_to_string(mode, binary, num_digits)
    while len(result) < width:
        result += " "
    return result

def fp_to_fp(mode, binary):
    (size, exp_size, man_size, imp_one, exp, man, sign, nan) = fp_conv_common(mode, binary)
    if nan == "-Inf":
        return float('-inf')
    elif nan == "+Inf":
        return float('inf')
    elif nan != None:
        return float('nan')

    i_part = 1
    frac_part = man & ~(1 << man_size)
    hex_rep = "%s0x%d.%xp%d" % (("+", "-")[sign], i_part, frac_part, exp)
    fnum = float.fromhex(hex_rep)
    return fnum
