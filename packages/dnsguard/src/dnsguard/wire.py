"""Minimal DNS wire-format helpers (RFC 1035).

Only what a filtering resolver needs: read the question out of a query, build
a response, and relay an upstream answer verbatim. No third-party dependency.
"""

import struct

HEADER_LEN = 12
MAX_NAME = 255
CLASS_IN = 1


class WireError(ValueError):
    """Raised when a DNS message cannot be parsed."""


def encode_name(name):
    """Encode a dotted name into label format."""
    out = bytearray()
    for label in name.rstrip(".").split("."):
        if not label:
            continue
        try:
            raw = label.encode("idna")
        except UnicodeError:
            raw = label.encode("ascii", "ignore")
        if not raw:
            continue
        if len(raw) > 63:
            raise WireError("label longer than 63 bytes")
        out.append(len(raw))
        out += raw
    out.append(0)
    if len(out) > MAX_NAME:
        raise WireError("name longer than 255 bytes")
    return bytes(out)


def decode_name(data, offset):
    """Decode a (possibly compressed) name.

    Returns (dotted_name, offset_just_past_the_name).
    """
    labels = []
    end = None
    seen = set()
    jumped = False
    while True:
        if offset >= len(data):
            raise WireError("name runs past end of message")
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end = offset
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise WireError("compression pointer runs past end of message")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end = offset + 2
            if pointer in seen:
                raise WireError("compression pointer loop")
            seen.add(pointer)
            offset = pointer
            jumped = True
            continue
        offset += 1
        if offset + length > len(data):
            raise WireError("label runs past end of message")
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
        if not jumped:
            end = offset
    return ".".join(labels), end


def parse_query(data):
    """Parse the header and question of a DNS query."""
    if len(data) < HEADER_LEN:
        raise WireError("message shorter than a DNS header")
    qid, flags, qdcount = struct.unpack(">HHH", data[:6])
    if qdcount < 1:
        raise WireError("query carries no question")
    if (flags >> 15) & 1:
        raise WireError("message is a response, not a query")
    qname, offset = decode_name(data, HEADER_LEN)
    if offset + 4 > len(data):
        raise WireError("question section is truncated")
    qtype, qclass = struct.unpack(">HH", data[offset:offset + 4])
    offset += 4
    return {
        "id": qid,
        "flags": flags,
        "opcode": (flags >> 11) & 0x0F,
        "rd": bool(flags & 0x0100),
        "qname": qname,
        "qtype": qtype,
        "qclass": qclass,
        "question_bytes": data[HEADER_LEN:offset],
        "arcount": struct.unpack(">H", data[10:12])[0],
    }


def build_response(qid, request_flags, question_bytes, rcode=0, answers=b"",
                   ancount=0, additional=b""):
    """Build a response that echoes the question verbatim."""
    flags = 0x8000
    flags |= request_flags & 0x7800
    flags |= 0x0400
    if request_flags & 0x0100:
        flags |= 0x0100
    flags |= 0x0080
    flags |= rcode & 0x0F
    header = struct.pack(">HHHHHH", qid, flags, 1, ancount, 0, 0)
    return header + question_bytes + answers + additional


def build_query(qid, qname, qtype, recursion_desired=True):
    """Build a standard recursive query."""
    flags = 0x0100 if recursion_desired else 0
    header = struct.pack(">HHHHHH", qid, flags, 1, 0, 0, 0)
    return header + encode_name(qname) + struct.pack(">HH", qtype, CLASS_IN)


def set_id(data, qid):
    """Return the message with its transaction id replaced."""
    if len(data) < 2:
        return data
    return struct.pack(">H", qid) + data[2:]


def is_truncated(data):
    """True when the TC bit is set."""
    if len(data) < 4:
        return False
    return bool(struct.unpack(">H", data[2:4])[0] & 0x0200)


def rcode(data):
    """Return the response code of a message (0 when unknown)."""
    if len(data) < 4:
        return 0
    return struct.unpack(">H", data[2:4])[0] & 0x0F
