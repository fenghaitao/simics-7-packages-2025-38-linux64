# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Parser for Apple disk image (DMG) files.
#



try:
    import simics
except ImportError:
    # OK if not running in Simics
    pass

import os
import io
import struct
import plistlib

def size_fmt(num):
    if num < 1024:
        return "%5d B" % num
    base = 10
    for unit in ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']:
        if (num >> base) <= 1024:
            mask = (1 << base) - 1
            if (num & mask) > 0:
                fpv = "%.1f" % round(float(num) / float(1 << base))
                return "%5s %s" % (fpv, unit)
            else:
                return "%5d %s" % (num >> base, unit)
        base += 10
    return "%3.1f YiB" % round(float(num) / float(1 << base))

class DmgError(Exception):
    """This is mainly intended for errors that are considered invalid for DMG files,
and thus the file should be considered corrupt."""
    def __init__(self, reason):
        self.msg = reason
    def __str__(self):
        return "DMG ERROR: %s" % self.msg

class NotDmgError(DmgError):
    """This exception is used for anything that indicates that the data cannot be
considered part of a DMG file. This will cause the image loader to fall-back to
raw format. """
    def __init__(self, reason):
        self.msg = reason
    def __str__(self):
        return "Not a DMG file: %s" % self.msg

class KolyTrailer:
    sectSize = 512  # Fixed size?
    kolySize = 512  # Fixed size!
    kolyPart = {
        "magic": slice(0, 4),  # "koly" magic identifier    offset [  0..  3]
        "basic": slice(4, 16),  #                           offset [  4.. 15]
        "forks": slice(16, 64),  #                          offset [ 16.. 63]
        "segm_id": slice(64, 80),  #                        offset [ 64.. 79]
        "data_csum": slice(80, 88),  #                      offset [ 80.. 87]
        # data checksum data - ignored                      offset [ 88..215]
        "plist": slice(0xd8, 0xe8),  # Property List XML    offset [216..231]
        # Reserved space - ignored                          offset [232..351]
        "master_csum": slice(0x160, 0x168),  #              offset [352..359]
        # master checksum data - ignored,                   offset [360..487]
        "img_nfo": slice(0x1e8, 0x1f4),  # Image info,      offset [488..499]
        # Reserved space - ignored,                         offset [500..511]
    }
    def __init__(self, trailer, dataEnd, debug=False):
        # dataEnd is also the offset of the 512 byte koly trailer block
        if not trailer[self.kolyPart["magic"]] == bytearray(b'koly'):
            raise NotDmgError('Cannot find the koly block')
        (self.version, self.size, self.flags) = (
            struct.unpack(">III", trailer[self.kolyPart["basic"]]))
        (self.runForkOff, self.dataForkOff, self.dataForkLen, self.resForkOff,
         self.resForkLen, self.segmNum, self.segmCnt) = (
             struct.unpack(">QQQQQII", trailer[self.kolyPart["forks"]]))
        (uh, ul) = struct.unpack(">QQ", trailer[self.kolyPart["segm_id"]])
        self.uuid = (uh << 64) + ul
        (self.dataCsumType, self.dataCsumSize) = (
            struct.unpack(">II", trailer[self.kolyPart["data_csum"]]))
        (self.xmlOff, self.xmlLen) = struct.unpack(
            ">QQ", trailer[self.kolyPart["plist"]])
        (self.mstCsumType, self.mstCsumSize) = (
            struct.unpack(">II", trailer[self.kolyPart["master_csum"]]))
        (self.imgVar, self.expSize) = (
            struct.unpack(">IQ", trailer[self.kolyPart["img_nfo"]]))
        if debug:
            print("KOLY: Version=%d, Size=%d, Flags=0x%x" % (
                self.version, self.size, self.flags))
            print("KOLY: Segment=%d/%d" % (self.segmNum, self.segmCnt))
            print("KOLY: Data %s @ 0x%x (run 0x%x)" % (
                size_fmt(self.dataForkLen), self.dataForkOff, self.runForkOff))
            print("KOLY: Resource %s @ 0x%x" % (
                size_fmt(self.resForkLen), self.resForkOff))
            print("KOLY: Data checksum type=%d, bits=%d" % (
                self.dataCsumType, self.dataCsumSize))
            print("KOLY: XML %s @ 0x%x" % (size_fmt(self.xmlLen), self.xmlOff))
            print("KOLY: Master checksum type=%d, bits=%d" % (
                self.mstCsumType, self.mstCsumSize))
            print("KOLY: Variant=%d, Expanded size %s" % (
                self.imgVar, size_fmt(self.expSize * self.sectSize)))
        # Verify correctness
        if self.version != 4:
            raise DmgError('Unsupported Koly version %d, expected 4'
                           % self.version)
        if self.size != KolyTrailer.kolySize:
            raise DmgError('Unexpected Koly trailer size %d, expected %d'
                           % (self.size, KolyTrailer.kolySize))
        if self.imgVar not in (1, 2):
            raise DmgError('Unsupported Koly image variant %d, expected'
                             ' either 1 or 2' % self.imgVar)
        dataSize = self.dataForkLen + self.resForkLen + self.xmlLen
        if self.dataForkOff + dataSize != dataEnd:
            raise DmgError('Lengths do not add up')
        if self.xmlOff + self.xmlLen != dataEnd:
            raise DmgError('XML section not in the end')
        if self.dataForkOff + self.dataForkLen > self.xmlOff:
            raise DmgError('Data and XML sections overlap')
        if self.resForkOff + self.resForkLen > self.xmlOff:
            raise DmgError('Resource and XML sections overlap')
        if self.resForkLen and (
                self.dataForkOff + self.dataForkLen > self.resForkOff):
            raise DmgError('Data and resource sections overlap')
    def get_xml_section(self):
        return (self.xmlOff, self.xmlLen)
    def get_koly_info(self):
        return (self.version, self.sectSize, self.flags, self.imgVar,
                self.expSize * self.sectSize)

class DmgProp:
    def __init__(self, text, debug=False):
        self.plist = plistlib.loads(text)
        resFork = self.plist.get('resource-fork', {})
        if not resFork:
            raise DmgError("Cannot find the 'resource-fork' in the properties")
        if debug:
            print("PLIST:", list(self.plist.keys()))
            print("PLIST Resources:", list(resFork.keys()))
        resBlkx = resFork.get('blkx', [])
        resPlst = resFork.get('plst', [])
        if debug:
            print("PLIST Resource Properties:")
            print('\n'.join(['\t' + x.get('Name') for x in resPlst]))
        self.blkx = {}
        for blkx in resBlkx:
            blk = BlkxTable(blkx, debug)
            self.blkx[blk.blkxid] = blk
    def get_blocks(self):
        return list(self.blkx.values())
    def get_block_by_id(self, bid):
        try:
            return self.blkx[bid]
        except IndexError:
            return None

class BlkxTable:
    blkxPart = {
        "magic": slice(0, 4),  # Magic identifier ("mish")  offset [  0..  3]
        "basic": slice(4, 40),  # Basic blkx info           offset [  4.. 39]
        # Reserved space - ignored                          offset [ 40.. 63]
        "csum": slice(64, 72),  # Blkx Checksum            offset [ 64.. 71]
        # Checksum data - ignored                           offset [ 72..199]
        "count": slice(200, 204), # Number of chunks        offset [200..203]
        # Chunk data follows
    }
    tableSize = 204
    def __init__(self, blkx, debug=False):
        self.blkxid = int(blkx.get('ID', '-1'))  # ID is always a number, AFAICT
        self.name = blkx.get('Name', '')
        self.cfname = blkx.get('CFName', '')
        self.attr = blkx.get('Attributes')
        data = blkx.get('Data')
        if not data:
            raise DmgError("The block contains no data")
        if debug:
            print("MISH: ID=%d, Name='%s'" % (self.blkxid, self.name))
        else:
            self.signature = data[self.blkxPart["magic"]]
        if self.signature != b'mish':
            raise DmgError("Invalid signature '%s', expected 'mish'"
                             % self.signature)
        (self.version, self.sectNum, self.sectCnt,
         self.dataOff, self.bufCnt, self.blkCnt) = (
             struct.unpack(">IQQQII", data[self.blkxPart["basic"]]))
        (self.destOff, self.destLen) = (self.sectNum << 9, self.sectCnt << 9)
        (self.csumType, self.csumSize) = struct.unpack(
            ">II", data[self.blkxPart["csum"]])
        (self.chunks,) = struct.unpack(">I", data[self.blkxPart["count"]])
        if debug:
            print("MISH: Version=%d, Size=%d" % (self.version, len(data)))
            print("MISH: Dest %s @ 0x%x [%d sector(s) @ %s]" % (
                size_fmt(self.destLen), self.destOff,
                self.sectCnt, self.sectNum))
            print("MISH: Data @ 0x%x, Buffers Needed %d, Blocks %d" % (
                self.dataOff, self.bufCnt, self.blkCnt))
            print("MISH: Checksum %d bits, type %d" % (
                self.csumSize, self.csumType))
            print("MISH: %d Chunks in [%d..%d]" % (
                self.chunks, self.tableSize, len(data) - 1))
        exptLen = self.tableSize + 40 * self.chunks
        if exptLen != len(data):
            raise DmgError("Blkx table data size %d, expected %d"
                             % (len(data), exptLen))
        self.chunk = []
        for off in range(self.tableSize, len(data), 40):
            self.chunk.append(BlkxChunk(data[off:off + 40], debug))
    def __str__(self):
        return "#%d:%s" % (self.blkxid, self.name)
    def get_sectors(self):
        return (self.sectNum, self.sectCnt)
    def get_dest(self):
        return (self.destOff, self.destLen)
    def get_chunks(self):
        return [c for c in self.chunk if c.get_type() not in ('CMNT', 'END')]
    def get_chunk_count(self):
        return len(self.chunk)
    def get_chunk(self, n):
        try:
            return self.chunk[n]
        except IndexError:
            return None

class BlkxChunk:
    chnkType = {
        0: 'ZERO',           # Data consisting only of zeroes
        1: 'RAW',            # Uncompressed data
        2: 'HOLE',           # Ignored data area, a hole in the data
        0x80000004: 'UDCO',  # Apple compression, not supported
        0x80000005: 'UDZO',  # Zip compression
        0x80000006: 'UDBZ',  # BZip2 compression, not supported
        0x80000007: 'UDLZ',  # LZFSE compression
        0x7ffffffe: 'CMNT',  # Comment
        0xffffffff: 'END',   # End token
    }
    def __init__(self, data, debug=False):
        (self.cType, self.rsvd, self.sectOff, self.sectCnt,
         self.compOff, self.compLen) = struct.unpack(">IIQQQQ", data)
        self.destOff = self.sectOff * KolyTrailer.sectSize
        self.destLen = self.sectCnt * KolyTrailer.sectSize
        if self.cType not in self.chnkType:
            raise DmgError("Unknown chunk type: 0x%x (%d)" % (self.cType, self.cType))
        if debug:
            ct = self.get_type()
            if ct in ('END', 'CMNT'):
                return
            elif ct in ('ZERO', 'HOLE'):
                print("CHNK:", str(self))
            elif ct == 'RAW':
                if self.compLen != self.destLen:
                    raise DmgError(
                        "Source and destination size mismatch for %s data:"
                        " %d <> %d" % (ct, self.compLen, self.destLen))
                print("CHNK: %s @ 0x%08x" % (str(self), self.compOff))
            elif ct in ('UDZO', 'UDLZ'):
                print("CHNK: %s @ 0x%08x %10s" % (
                    str(self), self.compOff, size_fmt(self.compLen)))
            else:
                raise DmgError("Unsupported chunk type: %s (0x%x)" % (
                    ct, self.cType))
    def __str__(self):
        return "@Sector %9d %5d sector%s (%10s) %4s" % (
            self.sectOff, self.sectCnt, "s" if self.sectCnt > 1 else " ",
            size_fmt(self.destLen), self.get_type())
    def get_type(self):
        return self.chnkType.get(self.cType, "---")
    def get_dest(self):
        return (self.destOff, self.destLen)
    def get_src(self):
        return (self.compOff, self.compLen)

def get_chunk_type(ct):
    return BlkxChunk.chnkType.get(ct, "---")

class DmgImage:
    def __init__(self, dmgfile, debug=False):
        if os.stat(dmgfile).st_size < KolyTrailer.kolySize:
            raise NotDmgError('File too small for the koly block')
        with open(dmgfile, 'rb') as dmg:
            dmg.seek(-KolyTrailer.kolySize, io.SEEK_END)
            self.dataEnd = dmg.tell()
            trailer = dmg.read()
            self.koly = KolyTrailer(trailer, self.dataEnd, debug)
            (xmlOff, xmlLen) = self.koly.get_xml_section()
            dmg.seek(xmlOff)
            self.prop = DmgProp(dmg.read(xmlLen), debug)
        self.src = []
        self.dest = []
    def _get_blocks(self):
        return self.prop.get_blocks()
    def get_block_strings_list(self):
        return [str(c) for c in self._get_blocks()]
    def get_block_info(self):
        bi = []
        for blk in self._get_blocks():
            bi.append((blk.blkxid, blk.name, len(blk.chunk) - 1))
        return bi
    def gen_dest_list(self):
        assert not self.dest
        for blk in self._get_blocks():
            (bOff, bLen) = blk.get_dest()
            for cnk in blk.get_chunks():
                (dOff, dLen) = cnk.get_dest()
                (sOff, sLen) = cnk.get_src()
                self.dest.append((dOff + bOff, dLen, cnk.cType, sOff, sLen))
        self.dest = sorted(self.dest, key=lambda s: s[0])
    def gen_src_list(self):
        assert not self.src
        if not self.dest:
            self.gen_dest_list()
        assert self.dest
        for (do, dl, st, so, sl) in self.dest:
            sType = get_chunk_type(st)
            if sType not in ('ZERO', 'HOLE'):
                self.src.append((so, sl, sType))
        self.src = sorted(self.src, key=lambda s: s[0])
    def validate(self):
        # Populate destination array
        if not self.dest:
            self.gen_dest_list()
        # Populate source array
        if not self.src:
            self.gen_src_list()
        assert self.dest
        assert self.src
        # Verify destination
        off = 0
        for (dOff, dLen, _, _, _) in self.dest:
            if dOff != off:
                raise DmgError("Got destination offset %d, expected %d"
                               % (dOff, off))
            off += dLen
        # Verify source
        off = 0
        for (sOff, sLen, _) in self.src:
            if sOff < off:
                raise DmgError("Got source offset %d, expected at least %d"
                               % (sOff, off))
            off = sOff + sLen
        if off > self.dataEnd:
            raise DmgError("Data offset %d is outside of data area end @ %d"
                           % (off, self.dataEnd))
    def print_dest(self):
        for (do, dl, st, so, sl) in self.dest:
            print("0x%08x..0x%08x %10s %4s 0x%08x %10s" % (
                do, do+dl-1, size_fmt(dl), get_chunk_type(st), so, size_fmt(sl)))
    def get_meta_info(self):
        (vers, sectsize, flags, imgvar, tsize) = self.koly.get_koly_info()
        return [vers, imgvar, sectsize, flags, self.dataEnd + self.koly.size,
                tsize]
    def get_chunk_list(self):
        return [[do, dl, st, so, sl] for (do, dl, st, so, sl) in self.dest]

def dmg_parse_file(imgname):
    try:
        dmg = DmgImage(imgname)
    except NotDmgError as e:
        return [imgname, 0, str(e)]
    except DmgError as e:
        return [imgname, 1, str(e)]
    dmg.gen_dest_list()
    dmg.validate()
    return [dmg.get_meta_info(), dmg.get_chunk_list()]
