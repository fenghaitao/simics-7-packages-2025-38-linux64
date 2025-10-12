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


# ehci_common.py
# definitions used by subtests

import dev_util as du
from simics import SIM_delete_object

Pointer_Type_iTD  = 0 #Isochronous Transfer Descriptor
Pointer_Type_QH   = 1 #Queue Head
Pointer_Type_siTD = 2 #Split Transaction Isochronous Transfer Descriptor
Pointer_Type_FSTN = 3 #Frame Span Traversal Node

qTD = {"NqTD": (0, 4, du.Bitfield_LE({'Ptr': (31, 5), 'T': 0})),
       "ANqTD": (4, 4, du.Bitfield_LE({'Ptr': (31, 5), 'T': 0})),
       "tState": (8, 4, du.Bitfield_LE({'dToggle': 31,
                                        'totBytes': (30, 16),
                                        'ioc': 15,
                                        'C_Page': (14, 12),
                                        'Cerr': (11,10),
                                        'PID_Code': (9, 8),
                                        'st_active': 7,
                                        'st_halted': 6,
                                        'st_data_buffer_error': 5,
                                        'st_babble_detected': 4,
                                        'st_xacterr': 3,
                                        'st_missed_mframe': 2,
                                        'st_spitxstate': 1,
                                        'st_ping_state': 0})),
       "page0": (12, 4, du.Bitfield_LE({'buffPtr': (31, 12),
                                        'currOffset': (11, 0)})),
       "page1": (16, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
       "page2": (20, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
       "page3": (24, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
       "page4": (28, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
       "extpage0": (32, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
       "extpage1": (36, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
       "extpage2": (40, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
       "extpage3": (44, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
       "extpage4": (48, 4, du.Bitfield_LE({'buffPtr': (31, 0)}))}

queueHead = {"QHPtr": (0, 4, du.Bitfield_LE({'QHLP': (31, 5),
                                             'Type': (2, 1),
                                             'T': 0})),
             "ECap0": (4, 4, du.Bitfield_LE({'RL': (31, 28),
                                             'C': 27,
                                             'MPL': (26, 16),
                                             'H': 15,
                                             'DTC': 14,
                                             'EPS': (13, 12),
                                             'Endpt': (11, 8),
                                             'I': 7,
                                             'DAddr': (6, 0)})),
             "ECap1": (8, 4, du.Bitfield_LE({'Mult': (31, 30),
                                             'PrtNbr': (29, 23),
                                             'HubAddr': (22, 16),
                                             'uFrCMsk': (15, 8),
                                             'uFrSMsk': (7, 0)})),
             "CqTD": (12, 4, du.Bitfield_LE({'Ptr': (31, 5)})),
             "NqTD": (16, 4, du.Bitfield_LE({'Ptr': (31, 5), 'T': 0})),
             "AqTD": (20, 4, du.Bitfield_LE({'Ptr': (31, 5),
                                             'NakCnt': (4, 1),
                                             'T': 0})),
             "tState": (24, 4, du.Bitfield_LE({'dToggle': 31,
                                               'totBytes': (30, 16),
                                               'ioc': 15,
                                               'C_Page': (14, 12),
                                               'Cerr': (11,10),
                                               'PID_Code': (9, 8),
                                               'st_active': 7,
                                               'st_halted': 6,
                                               'st_data_buffer_error': 5,
                                               'st_babble_detected': 4,
                                               'st_xacterr': 3,
                                               'st_missed_mframe': 2,
                                               'st_spitxstate': 1,
                                               'st_ping_state': 0})),
             "page0": (28, 4, du.Bitfield_LE({'buffPtr': (31, 12),
                                              'currOffset': (11, 0)})),
             "page1": (32, 4, du.Bitfield_LE({'buffPtr': (31, 12),
                                              'CProgMsk': (7, 0)})),
             "page2": (36, 4, du.Bitfield_LE({'buffPtr': (31, 12),
                                              'SByte': (11, 4),
                                              'FrTag': (3, 0)})),
             "page3": (40, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
             "page4": (44, 4, du.Bitfield_LE({'buffPtr': (31, 12)})),
             "extpage0": (48, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
             "extpage1": (52, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
             "extpage2": (56, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
             "extpage3": (60, 4, du.Bitfield_LE({'buffPtr': (31, 0)})),
             "extpage4": (64, 4, du.Bitfield_LE({'buffPtr': (31, 0)}))}

PID_Token_Out   = 0
PID_Token_In    = 1
PID_Token_Setup = 2
TimeInterval = 1000

Request = {"bmRequest": (0, 1, du.Bitfield_LE({'Dir': 7,
                                               'Type': (6, 5),
                                               'Recipient': (4, 0)})),
           "bRequest" : (1, 1),
           "wValue"   : (2, 2),
           "wIndex"   : (4, 2),
           "wLength"  : (6, 2)}
bRequestValue = {"Get Status"        : 0,
                 "Clear Feature"     : 1,
                 "Set Feature"       : 3,
                 "Set Address"       : 5,
                 "Get Descriptor"    : 6,
                 "Set Descriptor"    : 7,
                 "Get Configuration" : 8,
                 "Set Configuration" : 9,
                 "Get Interface"     : 10,
                 "Set Interface"     : 11,
                 "Sync Frame"        : 12}
DescTypeValue = {"Device"            : 1,
                 "Configuration"     : 2,
                 "String"            : 3,
                 "Interface"         : 4,
                 "Endpoint"          : 5,
                 "Device Qualifier"  : 6,
                 "OSp Configuration" : 7,
                 "Interface Power"   : 8}
FeatureValue = {"device rmt wakeup"  : ('Device', 1),
                "endpoint halt"      : ('Endpoint', 0),
                "Test mode"          : ('Device', 2)}

def calc_bp_values(data_base, c_page, total, offset):
    assert offset < 4096 and c_page < 5
    assert total <= ((5 - c_page) * 4096 - offset)
    bp = [0] * 5
    for p in range(c_page, 5):
        bp[p] = (data_base & 0xFFFFF000, bp[p - 1] + 0x1000)[p > c_page]
        len = 4096 - (0, offset)[p == c_page]
        if total <= len: break
        else: total -= len
    return bp

def conf_queue_head(qh, epn, PID, dbase, c_page, total, cqtd,
                    dToggle=0, offset=0, ioc=1, daddr=0, NqTD=None):
    bp = calc_bp_values(dbase, c_page, total, offset)
    qh.QHPtr.write(0, QHLP=0, Type=1, T=1) #next queue head is invalid
    qh.ECap0.write(0, H = 1, Endpt = epn, DAddr=daddr)
    qh.ECap1.write(0) # ignored by simics EHCI
    qh.CqTD.write(0, Ptr=cqtd>>5)  # update by EHCI

    if NqTD:
        qh.NqTD.write(0, Ptr=NqTD >> 5, T=0)
    else:
        qh.NqTD.write(0, Ptr=0, T=1)#one element only
    qh.AqTD.write(0, Ptr=0, T=1)#one element only
    qh.tState.write(0,
                    dToggle=dToggle,
                    Cerr=0,
                    st_halted=0,
                    st_data_buffer_error = 0,
                    st_babble_detected = 0,
                    st_xacterr = 0,
                    st_missed_mframe = 0,
                    st_spitxstate = 0,
                    st_ping_state = 0,
                    totBytes = total, # total bytes
                    ioc = ioc,      # interrupt on complete
                    C_Page = c_page,# current page
                    PID_Code = PID, # 0 Out 1 In 2 SETUP Token
                    st_active = 1)  # set 1 to execute transaction
    qh.page0.write(0, buffPtr=bp[0] >> 12, currOffset=offset)
    qh.page1.write(0, buffPtr=bp[1] >> 12)
    qh.page2.write(0, buffPtr=bp[2] >> 12)
    qh.page3.write(0, buffPtr=bp[3] >> 12)
    qh.page4.write(0, buffPtr=bp[4] >> 12)

def conf_qTD(qTD, PID, dbase, c_page, total,
                 dToggle=0, offset=0, ioc=1, NqTD=None):
    bp = calc_bp_values(dbase, c_page, total, offset)
    if NqTD:
        qTD.NqTD.write(0, Ptr=NqTD>>5, T=0)
    else:
        qTD.NqTD.write(0, T=1)
    qTD.ANqTD.write(0, T=1)
    qTD.tState.write(0,
                     dToggle=dToggle,
                     totBytes=total,
                     ioc=ioc,
                     C_Page=c_page,
                     Cerr=0,
                     PID_Code=PID,
                     st_halted=0,
                     st_active=1,
                     st_data_buffer_error=0,
                     st_babble_detected=0,
                     st_xacterr=0,
                     st_missed_mframe=0,
                     st_spitxstate=0,
                     st_ping_state=0)
    qTD.page0.write(0, buffPtr=bp[0]>>12, currOffset=offset)
    qTD.page1.write(0, buffPtr=bp[1]>>12)
    qTD.page2.write(0, buffPtr=bp[2]>>12)
    qTD.page3.write(0, buffPtr=bp[3]>>12)
    qTD.page4.write(0, buffPtr=bp[4]>>12)

def write_usb_request(mem, addr, out, type, recipient,
                      bRequest, wValue, wIndex, wLength):
    usbReq = du.Layout_LE(mem, addr, Request)
    usbReq.bmRequest.write(0, Dir = (1, 0)[out],
                           Type=type,
                           Recipient=recipient)
    usbReq.bRequest = bRequestValue[bRequest]
    usbReq.wValue   = wValue
    usbReq.wIndex   = wIndex
    usbReq.wLength  = wLength

def usbctrl_set_address(mem, usb_addr, new_addr, qaddr, daddr):
    qh_addr = qaddr
    qtd_addr = qaddr + 0x1000
    cqtd_addr = qaddr
    qh = du.Layout_LE(mem, qh_addr, queueHead)  #setup Token
    qh.clear()
    td = du.Layout_LE(mem, qtd_addr, qTD)  #In Token
    td.clear()

    conf_queue_head(qh, 0, PID_Token_Setup, daddr,
                    0, 8, cqtd_addr, daddr=usb_addr, NqTD=qtd_addr)
    conf_qTD(td, PID_Token_In, daddr, 0, 1, offset=8)

def usbdata_out(mem, usb_addr, epn, qaddr, daddr, total):
    qh_addr = qaddr
    cqtd_addr = qaddr + 64

    qh = du.Layout_LE(mem, qh_addr, queueHead) # Out Token
    qh.clear()

    conf_queue_head(qh, epn, PID_Token_Out, daddr,
                    0, total, cqtd_addr, dToggle=1, daddr = usb_addr)

def usbdata_in(mem, usb_addr, epn, qaddr, daddr, total):
    qh_addr = qaddr
    cqtd_addr = qh_addr + 64

    qh = du.Layout_LE(mem, qh_addr, queueHead) # In Token
    conf_queue_head(qh, epn, PID_Token_In, daddr,
                    0, total, cqtd_addr, dToggle=1, daddr = usb_addr)

# Remove the usb devices
def remove_usb_devices(n_ehci, n_ports, usb_device):
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            usb_device[k].device_connection = False
            SIM_delete_object(usb_device[k])
