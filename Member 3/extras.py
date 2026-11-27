"""Website extras built on top of Member 1's and Member 2's carriers.

1. Self-destruct date. The date is written in front of the message *before* it
   is hidden, so it travels inside the hidden payload. With a password that
   payload is encrypted and authenticated (AES-256-GCM), so the date cannot be
   read or changed without breaking the message. The website refuses to reveal
   after that date. (Someone with the password and the raw algorithm could
   still read it: the check lives in the website, not in the maths.)

2. Split secret (2-of-2 XOR secret sharing). A random pad R as long as the
   message is made; part 1 holds R and part 2 holds message XOR R. Each part on
   its own is uniformly random, so one picture alone says nothing about the
   message; XOR-ing both parts gives it back.

3. QR code of a stego text, so it can be scanned on a phone.

4. Spread over several pictures: a message too long for one picture is cut
   into numbered pieces, one per picture; Reveal needs all of them.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

# ------------------------------------------------------------ self-destruct
_EXP = "\x1eexp="          # record-separator, then the date, then another separator
_SEP = "\x1e"


def wrap_expiry(message: str, expires: datetime | None) -> str:
    if expires is None:
        return message
    return f"{_EXP}{expires.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}{_SEP}{message}"


def unwrap_expiry(message: str) -> tuple[str, datetime | None]:
    """Split a revealed message into (text, expiry). Messages without a date pass through."""
    if not message.startswith(_EXP):
        return message, None
    end = message.find(_SEP, len(_EXP))
    if end < 0:
        return message, None
    try:
        when = datetime.strptime(message[len(_EXP):end], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return message, None
    return message[end + 1:], when


# ------------------------------------------------------------ split secret
SPLIT_MAGIC = b"\x1fSPLIT1"
_ID = 8


def split_secret(secret: bytes) -> tuple[bytes, bytes]:
    """Two shares; each is MAGIC + id + part number + body. Bodies: R and secret XOR R."""
    pad = os.urandom(len(secret))
    other = bytes(a ^ b for a, b in zip(secret, pad))
    ident = os.urandom(_ID)
    return (SPLIT_MAGIC + ident + b"\x01" + pad,
            SPLIT_MAGIC + ident + b"\x02" + other)


def parse_share(data: bytes) -> tuple[bytes, int, bytes] | None:
    """(id, part, body) when data is a share, otherwise None."""
    head = len(SPLIT_MAGIC) + _ID + 1
    if not data.startswith(SPLIT_MAGIC) or len(data) < head or data[head - 1] not in (1, 2):
        return None
    return data[len(SPLIT_MAGIC):head - 1], data[head - 1], data[head:]


class ShareMismatch(ValueError):
    pass


def join_shares(a: bytes, b: bytes) -> bytes:
    pa, pb = parse_share(a), parse_share(b)
    if not pa or not pb:
        raise ShareMismatch("Both pictures must be halves of a split message.")
    if pa[0] != pb[0] or len(pa[2]) != len(pb[2]):
        raise ShareMismatch("These two halves belong to different messages.")
    if pa[1] == pb[1]:
        raise ShareMismatch("That is the same half twice. Add the other half.")
    return bytes(x ^ y for x, y in zip(pa[2], pb[2]))


# ------------------------------------------------------------ spread over several pictures
# When a message is too long for one picture it is cut into pieces, one per picture.
# Each piece: MAGIC + id + piece number + number of pieces + bytes. Reveal needs every piece.
CHAIN_MAGIC = b"\x1fCHAIN1"
CHAIN_HEAD = len(CHAIN_MAGIC) + _ID + 2      # 17 bytes of every picture's room go to this label
MAX_PICTURES = 10


def chain_pieces(secret: bytes, room: list[int]) -> list[tuple[int, bytes]] | None:
    """Cut secret to fit pictures with the given room (bytes each), in order.

    Returns [(picture index, piece)] using only as many pictures as needed, or None if they are not enough.
    """
    ident, cuts, pos = os.urandom(_ID), [], 0
    for i, r in enumerate(room):
        if pos >= len(secret):
            break
        take = r - CHAIN_HEAD
        if take <= 0:
            continue                              # a picture too small to help is skipped
        cuts.append((i, secret[pos:pos + take]))
        pos += take
    if pos < len(secret) or len(cuts) > 255:
        return None
    total = len(cuts)
    return [(i, CHAIN_MAGIC + ident + bytes([k, total]) + body) for k, (i, body) in enumerate(cuts)]


def parse_piece(data: bytes) -> tuple[bytes, int, int, bytes] | None:
    """(id, piece number, number of pieces, body) when data is a piece, otherwise None."""
    if not data.startswith(CHAIN_MAGIC) or len(data) < CHAIN_HEAD:
        return None
    k, total = data[CHAIN_HEAD - 2], data[CHAIN_HEAD - 1]
    if total == 0 or k >= total:
        return None
    return data[len(CHAIN_MAGIC):CHAIN_HEAD - 2], k, total, data[CHAIN_HEAD:]


def join_pieces(datas: list[bytes]) -> bytes:
    """Put the pieces back in order. Raises ShareMismatch naming what is missing."""
    pieces = [parse_piece(d) for d in datas]
    if not all(pieces):
        raise ShareMismatch("One of these pictures is not part of this message.")
    ident, total = pieces[0][0], pieces[0][2]
    if any(p[0] != ident or p[2] != total for p in pieces):
        raise ShareMismatch("These pictures belong to different messages.")
    have = {p[1]: p[3] for p in pieces}
    missing = [k + 1 for k in range(total) if k not in have]
    if missing:
        names = str(missing[0]) if len(missing) == 1 else ", ".join(map(str, missing[:-1])) + f" and {missing[-1]}"
        word = "picture" if len(missing) == 1 else "pictures"
        raise ShareMismatch(f"This message is spread over {total} pictures. Add {word} {names} of {total}.")
    return b"".join(have[k] for k in range(total))


def combine(raws: list[bytes]) -> bytes:
    """Rebuild a message from what was read out of several pictures, given in any order.

    A normal message comes back as is; two split halves are XOR-ed; spread pieces are put
    back in their numbered order. Raises ShareMismatch saying what is missing or wrong.
    """
    shares = [r for r in raws if parse_share(r)]
    pieces = [r for r in raws if parse_piece(r)]
    plain = [r for r in raws if not parse_share(r) and not parse_piece(r)]
    if not shares and not pieces:
        return plain[0]
    if plain or (shares and pieces):
        raise ShareMismatch("These pictures belong to different messages.")
    if shares:
        if len(shares) == 1:
            raise ShareMismatch("This picture holds half of a split message. Add the other half.")
        if len(shares) > 2:
            raise ShareMismatch("A split message has exactly two halves. Remove the extra pictures.")
        return join_shares(*shares)
    return join_pieces(pieces)


# ------------------------------------------------------------ QR code
class QrTooLong(ValueError):
    pass


def qr_png_data_uri(text: str) -> str:
    import segno
    try:
        qr = segno.make(text, error="l", micro=False)   # lowest error level holds the most
    except segno.DataOverflowError as exc:
        raise QrTooLong("This text is too long for a QR code. Use a shorter message or cover.") from exc
    return qr.png_data_uri(scale=8, border=3)


def png_data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
