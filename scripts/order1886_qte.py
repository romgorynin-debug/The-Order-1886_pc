#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# QTE edit from theorder1886-port, user-supplied TheOrder1886-Orbis.xml.
# Adapted from the user's tested QTE adapter; patches only derived PS4BOOT5.
import hashlib
import re
import struct
from pathlib import Path

EBOOT_SHA = 'a8ce5fe151573dca0b3951e1edfd608b3e027b53cc30761f7805e44c9d9ddec0'
PATTERN = bytes.fromhex('c5 fa 10 0d 00 00 00 00 76 08 c5 fa 59 0d 00 00 00 00 c5 fa 11 4d')
MASK = bytes([1]*4+[0]*4+[1]*6+[0]*4+[1]*4)
AT = 8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_image(raw):
    """Locate a unique signature in executable segments of the main image only."""
    require(len(raw) >= 112, 'Truncated PS4BOOT5 file')
    magic, size, entry, ns, nr, ni, flags = struct.unpack_from('<8s6Q', raw)
    require(magic == b'PS4BOOT5' and 0 < size <= 512*1024*1024 and entry < size
            and 0 < ns <= 64 and nr <= 1000000 and ni <= 100000 and flags <= 1,
            'Unsupported PS4BOOT5 header')
    nm, = struct.unpack_from('<Q', raw, 96)
    require(1 <= nm <= 64, 'Invalid module table')
    pos = 104 + nm*56
    require(pos+8 <= len(raw), 'Truncated module table')
    module_bases = [struct.unpack_from('<Q', raw, 104+i*56)[0] for i in range(nm)]
    main_end = min(module_bases)
    require(0 < main_end < size, 'Invalid main image boundary')
    nb, = struct.unpack_from('<Q', raw, pos)
    require(nb <= ni, 'Invalid binding count')
    segpos = pos+8+nb*24
    imagepos = segpos+ns*24+ni*128+nr*32
    require(imagepos+size == len(raw), 'Unexpected PS4BOOT5 layout or trailer')
    image = raw[imagepos:]
    # Lookahead preserves overlapping matches. Both original and already-edited forms
    # are counted so an ambiguous/already-patched source is refused.
    regex = b''.join((b'[\\x76\\xeb]' if i == AT else re.escape(bytes([b])) if MASK[i] else b'.')
                     for i,b in enumerate(PATTERN))
    matches = set()
    for i in range(ns):
        start, length, prot = struct.unpack_from('<3Q', raw, segpos+i*24)
        require(start <= size and length <= size-start and prot <= 7, 'Invalid segment')
        if prot & 1 and start < main_end:
            end = min(start+length, main_end)
            matches.update(m.start()+start for m in re.finditer(b'(?='+regex+b')', image[start:end], re.DOTALL))
    require(len(matches) == 1, f'QTE signature: expected 1 match, found {len(matches)}; no patch made')
    rva = matches.pop()+AT
    require(image[rva:rva+2] == b'\x76\x08', 'QTE site is already patched or unexpected; no patch made')
    result = bytearray(raw)
    result[imagepos+rva] = 0xeb
    return bytes(result), rva, imagepos+rva


RECIPE_ID = 'personal-qte-button-mash-v1'


def wanted(metadata, eboot_sha256, frame_rate):
    # Verified by the player on this precise CUSA00076 1.02 executable at 60 FPS.
    return (metadata.get('TITLE_ID') == 'CUSA00076' and metadata.get('APP_VER') == '01.02'
            and eboot_sha256 == EBOOT_SHA and frame_rate == 60)


def apply(path):
    path = Path(path)
    raw = path.read_bytes()
    patched, rva, offset = patch_image(raw)
    temp = path.with_name(path.name + '.qte.tmp')
    try:
        temp.write_bytes(patched)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return {'id': RECIPE_ID, 'applied': True, 'rva': hex(rva), 'file_offset': hex(offset),
            'before': '76', 'after': 'eb', 'before_sha256': sha(raw), 'after_sha256': sha(patched),
            'gameplay_verified': False}
