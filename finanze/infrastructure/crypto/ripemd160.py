import struct

_K_LEFT = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
_K_RIGHT = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]

_R_LEFT = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    7,
    4,
    13,
    1,
    10,
    6,
    15,
    3,
    12,
    0,
    9,
    5,
    2,
    14,
    11,
    8,
    3,
    10,
    14,
    4,
    9,
    15,
    8,
    1,
    2,
    7,
    0,
    6,
    13,
    11,
    5,
    12,
    1,
    9,
    11,
    10,
    0,
    8,
    12,
    4,
    13,
    3,
    7,
    15,
    14,
    5,
    6,
    2,
    4,
    0,
    5,
    9,
    7,
    12,
    2,
    10,
    14,
    1,
    3,
    8,
    11,
    6,
    15,
    13,
]

_R_RIGHT = [
    5,
    14,
    7,
    0,
    9,
    2,
    11,
    4,
    13,
    6,
    15,
    8,
    1,
    10,
    3,
    12,
    6,
    11,
    3,
    7,
    0,
    13,
    5,
    10,
    14,
    15,
    8,
    12,
    4,
    9,
    1,
    2,
    15,
    5,
    1,
    3,
    7,
    14,
    6,
    9,
    11,
    8,
    12,
    2,
    10,
    0,
    4,
    13,
    8,
    6,
    4,
    1,
    3,
    11,
    15,
    0,
    5,
    12,
    2,
    13,
    9,
    7,
    10,
    14,
    12,
    15,
    10,
    4,
    1,
    5,
    8,
    7,
    6,
    2,
    13,
    14,
    0,
    3,
    9,
    11,
]

_S_LEFT = [
    11,
    14,
    15,
    12,
    5,
    8,
    7,
    9,
    11,
    13,
    14,
    15,
    6,
    7,
    9,
    8,
    7,
    6,
    8,
    13,
    11,
    9,
    7,
    15,
    7,
    12,
    15,
    9,
    11,
    7,
    13,
    12,
    11,
    13,
    6,
    7,
    14,
    9,
    13,
    15,
    14,
    8,
    13,
    6,
    5,
    12,
    7,
    5,
    11,
    12,
    14,
    15,
    14,
    15,
    9,
    8,
    9,
    14,
    5,
    6,
    8,
    6,
    5,
    12,
    9,
    15,
    5,
    11,
    6,
    8,
    13,
    12,
    5,
    12,
    13,
    14,
    11,
    8,
    5,
    6,
]

_S_RIGHT = [
    8,
    9,
    9,
    11,
    13,
    15,
    15,
    5,
    7,
    7,
    8,
    11,
    14,
    14,
    12,
    6,
    9,
    13,
    15,
    7,
    12,
    8,
    9,
    11,
    7,
    7,
    12,
    7,
    6,
    15,
    13,
    11,
    9,
    7,
    15,
    11,
    8,
    6,
    6,
    14,
    12,
    13,
    5,
    14,
    13,
    13,
    7,
    5,
    15,
    5,
    8,
    11,
    14,
    14,
    6,
    14,
    6,
    9,
    12,
    9,
    12,
    5,
    15,
    8,
    8,
    5,
    12,
    9,
    12,
    5,
    14,
    6,
    8,
    13,
    6,
    5,
    15,
    13,
    11,
    11,
]

_MASK32 = 0xFFFFFFFF


def _f(j: int, x: int, y: int, z: int) -> int:
    if j < 16:
        return x ^ y ^ z
    elif j < 32:
        return (x & y) | (~x & z) & _MASK32
    elif j < 48:
        return (x | ~y & _MASK32) ^ z
    elif j < 64:
        return (x & z) | (y & ~z) & _MASK32
    else:
        return x ^ (y | ~z & _MASK32)


def _rotl32(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & _MASK32


def ripemd160(data: bytes) -> bytes:
    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0

    msg = bytearray(data)
    msg_len = len(data)
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0x00)
    msg += struct.pack("<Q", msg_len * 8)

    for i in range(0, len(msg), 64):
        block = msg[i : i + 64]
        x = list(struct.unpack("<16I", block))

        al, bl, cl, dl, el = h0, h1, h2, h3, h4
        ar, br, cr, dr, er = h0, h1, h2, h3, h4

        for j in range(80):
            rnd = j >> 4

            fl = _f(j, bl, cl, dl)
            t = (al + fl + x[_R_LEFT[j]] + _K_LEFT[rnd]) & _MASK32
            t = (_rotl32(t, _S_LEFT[j]) + el) & _MASK32
            al = el
            el = dl
            dl = _rotl32(cl, 10)
            cl = bl
            bl = t

            fr = _f(79 - j, br, cr, dr)
            t = (ar + fr + x[_R_RIGHT[j]] + _K_RIGHT[rnd]) & _MASK32
            t = (_rotl32(t, _S_RIGHT[j]) + er) & _MASK32
            ar = er
            er = dr
            dr = _rotl32(cr, 10)
            cr = br
            br = t

        t = (h1 + cl + dr) & _MASK32
        h1 = (h2 + dl + er) & _MASK32
        h2 = (h3 + el + ar) & _MASK32
        h3 = (h4 + al + br) & _MASK32
        h4 = (h0 + bl + cr) & _MASK32
        h0 = t

    return struct.pack("<5I", h0, h1, h2, h3, h4)
