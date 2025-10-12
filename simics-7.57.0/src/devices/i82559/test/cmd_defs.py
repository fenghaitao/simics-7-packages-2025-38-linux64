# cmd_defs.py
# Definition of command unit and receive frame structs for testing.

# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from configuration import *
import sys, os
sys.path.append(os.path.join("..", "common"))
import dev_util, etc_util

eth_frame   = [
#Destination MAC address (6 Bytes)
   # 0xff, 0xff, 0xff, 0xff,
   # 0xff, 0xff, 0x00, 0x13,
    0x00, 0x14, 0x73, 0xED,
    0x92, 0x64, 0x00, 0x13,
#Source MAC address (6 Bytes)
    0x72, 0xEC, 0x91, 0x63,
 #E-type(TCP/IP)
    0x08, 0x00,
# IP Header
 #TOS #IHL  #IP Version (V4)
    0x00, 0x54,
 #Total Length
    0x00, 0x30,
 #Identification
    0x00, 0x00,
 #Fragment offset #Flags
    0x00, 0x02,
 #Protocol #TTL(1000)
    0x06, 0xFF,
 #CheckSum
    0xD4, 0x9,
 #Source IP Address (192.168.1.16) (C0.A8.1.10)
    0xC0, 0xA8, 0x01, 0x10,
 #Destination IP Address (192.168.1.111) (C0.A8.1.6F)
    0xC0, 0xA8, 0x1, 0x6F,
#TCP header
 #source port 0x222 #destination port 0x111
    0x02, 0x22, 0x1, 0x11,
 #sequence number
    0x00, 0x00, 0x00, 0x00,
 #Acknowledge number
    0x00, 0x00, 0x00, 0x00,
    0xCC, 0xCC, 0xCC, 0xCC,
    0xDD, 0xDD, 0xDD, 0xDD,
    0xEE, 0xEE, 0xEE, 0xEE,
    0xFF, 0xFF, 0xFF, 0xFF,
    0xED, 0xED
]

# this is a frame less than 64 bytes used to passed in, to verify tx padding
eth_frame_short   = [
#Destination MAC address (6 Bytes)
    0x00, 0x14, 0x73, 0xED, 0x92, 0x64,
#Source MAC address (6 Bytes)
    0x00, 0x13, 0x72, 0xEC, 0x91, 0x63,
 #E-type(TCP/IP)
    0x08, 0x00,
# IP Header
 #TOS #IHL  #IP Version (V4)
    0x00, 0x54,
 #Total Length
    0x00, 0x30,
 #Identification
    0x00, 0x00,
]

# this is the frame above, after having been padded
eth_frame_short_pad   = [
#Destination MAC address (6 Bytes)
    0x00, 0x14, 0x73, 0xED,
    0x92, 0x64, 0x00, 0x13,
#Source MAC address (6 Bytes)
    0x72, 0xEC, 0x91, 0x63,
 #E-type(TCP/IP)
    0x08, 0x00,
# IP Header
 #TOS #IHL  #IP Version (V4)
    0x00, 0x54,
 #Total Length
    0x00, 0x30,
 #Identification
    0x00, 0x00,
 # pad data with 40 bytes
    0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e,
    0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e,
    0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e,
    0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e, 0x7e,
]



eth_frame_db = etc_util.eth_to_db(eth_frame)

cfg_para   = [
    22,   0x66,
    0x00, 0x0f,
    0x14, 0x94,
    0xFE, 0x47,
    0x01, 0x00,
    0x06, 0x00,
    0x01, 0x00,
    0xF2, 0x48,
    0x00, 0x00,
    0x80, 0x00,
    0x1F, 0x05
]

CU_DICT = {
    #command : [opcode, buffer_length]
    'NOP'                : [0x0 , 8  ] ,
    'Set_IA'             : [0x1 , 16 ] ,
    'Config'             : [0x2 , 9  ] ,
    'Set_Multicast_Addr' : [0x3 , 12 ] ,
    'TX'                 : [0x4 , 16 ] ,
    'Load_Microcode'     : [0x5 , 264] ,
    'Dump'               : [0x6 , 12 ] ,
    'Diagnose'           : [0x7 , 8  ]
}

class cu_generic:
    '''Generic cu'''
    def __init__(self, cmd):
        # Construct a new command
        if not cmd in CU_DICT:
            raise Exception("Cmd Error")
        self.cmd    = cmd
        self.cu_buf = list(0 for i in range( CU_DICT[cmd][1]) )
        self.len    = CU_DICT[cmd][1]
        cmd_val     = CU_DICT[cmd][0] & 0x7
        self.cu_buf[2]  = cmd_val
        self.ok     = 0
        self.c      = 0
        self.link_addr = 0
        if (self.cmd == "TX"):
            self.u   = 0

    def update_status_from_memory(self, buf):
        #make sure this is the same RU
        #assert CU_DICT[self.cmd][0] == etc_util.bytes_to_value_le8(buf[2:3]) & 0x7
        assert CU_DICT[self.cmd][0] == buf[2] & 0x7
        assert self.link_addr == etc_util.bytes_to_value_le32(buf[4:8])
        status   = etc_util.bytes_to_value_le16(buf[0:2])
        self.ok  = (status & (0x1 << 13)) >> 13
        self.c   = (status & (0x1 << 15)) >> 15
        if (self.cmd == "TX"):
            self.u   = (status & (0x1 << 12)) >> 12
        self.cu_buf[0:2] = buf[0:2]

    #General methods
    def set_el(self):
        self.cu_buf[3] |= 0x80

    def clear_el(self):
        self.cu_buf[3] &= ~0x80

    def set_s(self):
        self.cu_buf[3] |= 0x40

    def clear_s(self):
        self.cu_buf[3] &= ~0x40

    def set_i(self):
        self.cu_buf[3] |= 0x20

    def clear_i(self):
        self.cu_buf[3] &= ~0x20

    def set_link_addr_val(self, addr): #set cu link address
        self.cu_buf[4:8] = etc_util.value_to_bytes_le32(addr)
        self.link_addr   = addr

    def get_link_addr(self): #get cu link address
        return self.link_addr

    def get_c(self):
        return self.c

    def clear_c(self):
        self.c = 0
        self.cu_buf[1] &= ~0x80

    def get_ok(self):
        return self.ok

    def get_el(self):
        return (self.cu_buf[3] & 0x80) >> 7

    def is_last(self):
        if self.cu_buf[3] & 0x80 :
            return True
        else :
            return False

class cu_tx(cu_generic):
    '''Transmit command'''
    def __init__(self, cmd = 'TX'):
        cu_generic.__init__(self, cmd)

    def set_cid_val(self, cid):
        self.cu_buf[3] &= ~0x1F
        self.cu_buf[3] |= cid & 0x1F

    def set_nc(self):
        self.cu_buf[2] |= 0x10

    def clear_nc(self):
        self.cu_buf[2] &= ~0x10

    def set_sf(self):
        self.cu_buf[2] |= 0x08

    def clear_sf(self):
        self.cu_buf[2] &= ~0x08

    def set_tbd_addr_val(self, addr): #set TBD address
        self.cu_buf[8:12] = etc_util.value_to_bytes_le32(addr)

    def set_tbd_num_val(self, num):  #set TBD number
        self.cu_buf[15] = num & 0xff

    def set_thre_val(self, val):  #set transmit threshold value
        self.cu_buf[14] = val & 0xff

    def set_tbd_eof(self):  #set EOF bit
        self.cu_buf[13] |= 0x80

    def clear_tbd_eof(self):  #clear EOF bit
        self.cu_buf[13] &= ~0x80

    def set_tcb_count_val(self, cnt):  #set TCB byte count value
        self.cu_buf[12] &= ~0x3FFF
        self.cu_buf[12] |= cnt & 0x3FFF

    def get_status_u(self):
        return self.u

    def add_payload(self, buf):
        self.cu_buf += buf
        self.len += buf.__len__()

class cu_ia(cu_generic):
    '''Individual Address Setup'''
    def __init__(self, cmd = 'Set_IA'):
        cu_generic.__init__(self, cmd)

    def set_ia(self, tup_add):
        self.cu_buf[8:14] = tup_add

class cu_nop(cu_generic):
    '''NOP command'''
    def __init__(self, cmd = 'NOP'):
        cu_generic.__init__(self, cmd)

class cu_cfg(cu_generic):
    '''Configuration command'''
    def __init__(self, cmd = 'Config'):
        cu_generic.__init__(self, cmd)
        self.byte_count = 0

    def set_parameters(self, para):
        assert para.__len__() <= 22
        assert para[0] == list(para).__len__()
        byte_count = para[0] & 0x3f
        self.cu_buf[8] = byte_count
        self.cu_buf   += para[1:]
        self.byte_count = byte_count
        self.len += byte_count - 1

    def get_byte_count(self) :
        return self.byte_count

class cu_set_multicast_addr(cu_generic):
    '''Set Multicast Address command'''
    def __init__(self, cmd = 'Set_Multicast_Addr'):
        cu_generic.__init__(self, cmd)
        self.count = 0

    def add_multicast_addr(self, addr):
        if self.count + 1 > 0x3FFF :
            print("Can't add, the address list is full!")
            return
        self.count += 1
        self.cu_buf[8:10] = self.count
        self.cu_buf += list(etc_util.value_to_bytes_le32(addr))
        self.len += 4

class cu_dump(cu_generic):
    '''Dump command'''
    def __init__(self, cmd = 'Dump'):
        cu_generic.__init__(self, cmd)
        self.dump_addr = 0

    def set_dump_addr(self, addr):
        self.dump_addr = addr
        self.cu_buf[8:12] = etc_util.value_to_bytes_le32(addr)

class cu_diagnose(cu_generic):
    '''Diagnose command'''
    def __init__(self, cmd = 'Diagnose'):
        cu_generic.__init__(self, cmd)

class cu_load_microcode(cu_generic):
    '''Load Microcode command'''
    def __init__(self, cmd = 'Load_Microcode'):
        cu_generic.__init__(self, cmd)

    def set_microcode(self, code):
        self.cu_buf[8:264] = code[0:256]

class tbd_table:
    '''Transmit Buffer Descriptor Table'''
    def __init__(self):
        self.tbd = []
        self.num = 0

    def add_tbd(self, tbd_addr, size, el):
        self.tbd = self.tbd + list(etc_util.value_to_bytes_le32(tbd_addr))
        self.tbd = self.tbd + list(etc_util.value_to_bytes_le16(size & 0x7FFF))
        self.tbd = self.tbd + list(etc_util.value_to_bytes_le16(el & 0x1))
        self.num += 1

class ru_rfd:
    '''RU Simple Receive Frame Descriptor'''
    def __init__(self, size):
        assert size >=16
        self.size = size & 0x3FFF
        self.ru_buf = list(0 for i in range(size))
        self.ru_buf[14:16] = etc_util.value_to_bytes_le16(size)
        self.link_addr = 0
        self.status_bits = 0
        self.actual_count = 0
        self.ok  = 0
        self.c   = 0
        self.eof = 0
        self.f   = 0

    def update_status_from_memory(self, buf):
        #make sure this is the same RFD
        assert self.size      == etc_util.bytes_to_value_le16(buf[14:16])
        assert self.link_addr == etc_util.bytes_to_value_le32(buf[4:8])
        assert self.ru_buf.__len__() == buf.__len__()

        self.status_bits   = etc_util.bytes_to_value_le16(buf[0:2])
        self.ok            = (self.status_bits & (0x1 << 13)) >> 13
        self.c             = (self.status_bits & (0x1 << 15)) >> 15
        self.status_bits   = self.status_bits & 0x1FFF
        self.actual_count  = etc_util.bytes_to_value_le16(buf[12:14])
        self.f             = (self.actual_count & (0x1 << 12)) >> 12
        self.eof           = (self.actual_count & (0x1 << 15)) >> 15
        self.actual_count  = self.actual_count & 0x3FFF
        self.ru_buf[0:2]   = buf[0:2]
        self.ru_buf[12:14] = buf[12:14]
        self.ru_buf[16:self.actual_count+16]   = buf[16:self.actual_count+16]

    def set_link_addr_val(self, addr):
        self.ru_buf[4:8] = etc_util.value_to_bytes_le32(addr)
        self.link_addr = addr

    def get_link_addr(self):
        return self.link_addr

    #def set_sf(self): #Not support
     #   self.ru_buf[2] |= 0x08

    #def clear_sf(self):
    #    self.ru_buf[2] &= ~0x08

    def set_h(self):
        self.ru_buf[2] |= 0x10

    def clear_h(self):
        self.ru_buf[2] &= ~0x10

    def set_s(self):
        self.ru_buf[3] |= 0x40

    def clear_s(self):
        self.ru_buf[3] &= ~0x40

    def set_el(self):
        self.ru_buf[3] |= 0x80

    def clear_el(self):
        self.ru_buf[3] &= ~0x80

    def get_eof(self):
        return self.eof

    def clear_eof(self):
        self.ru_buf[13] &= ~0x80

    def get_f(self):
        return self.f

    def clear_f(self):
        self.ru_buf[13] &= ~0x40

    def get_ok(self):
        return self.ok

    def get_c(self):
        return self.c

    def get_status_bits(self):
        return self.status_bits

    def get_actual_count(self):
        return self.actual_count

    def is_last(self):
        if self.ru_buf[3] & 0x80 :
            return True
        else :
            return False
