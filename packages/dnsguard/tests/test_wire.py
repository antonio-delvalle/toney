import unittest

from dnsguard import wire


class EncodeNameTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(wire.encode_name("example.net"), b"\x07example\x03net\x00")

    def test_trailing_dot_is_ignored(self):
        self.assertEqual(wire.encode_name("example.net."), wire.encode_name("example.net"))

    def test_empty_name(self):
        self.assertEqual(wire.encode_name(""), b"\x00")

    def test_long_label_is_rejected(self):
        with self.assertRaises(wire.WireError):
            wire.encode_name("a" * 64 + ".net")


class DecodeNameTests(unittest.TestCase):
    def test_round_trip(self):
        name, offset = wire.decode_name(wire.encode_name("ads.example.net"), 0)
        self.assertEqual(name, "ads.example.net")
        self.assertEqual(offset, len(wire.encode_name("ads.example.net")))

    def test_compression_pointer(self):
        full = b"\x00\x00\x03www\x07example\x03com\x00"
        compressed = b"\x03www\xc0\x0c" + full
        name, offset = wire.decode_name(compressed, 0)
        self.assertEqual(name, "www.example.com")
        self.assertEqual(offset, 6)

    def test_truncated_message(self):
        with self.assertRaises(wire.WireError):
            wire.decode_name(b"\x07exam", 0)


class ParseQueryTests(unittest.TestCase):
    def _query(self, name="ads.example.net", qtype=1):
        return wire.build_query(0x1234, name, qtype)

    def test_parses_question(self):
        query = wire.parse_query(self._query())
        self.assertEqual(query["id"], 0x1234)
        self.assertEqual(query["qname"], "ads.example.net")
        self.assertEqual(query["qtype"], 1)
        self.assertTrue(query["rd"])

    def test_rejects_response(self):
        response = wire.build_response(1, 0x0100, b"\x00", rcode=0)
        with self.assertRaises(wire.WireError):
            wire.parse_query(response)

    def test_rejects_short_message(self):
        with self.assertRaises(wire.WireError):
            wire.parse_query(b"\x00\x01")

    def test_rejects_query_without_question(self):
        with self.assertRaises(wire.WireError):
            wire.parse_query(b"\x12\x34\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00")


class BuildResponseTests(unittest.TestCase):
    def test_sets_response_bit_and_rcode(self):
        query = wire.build_query(9, "a.example", 1)
        parsed = wire.parse_query(query)
        response = wire.build_response(parsed["id"], parsed["flags"],
                                       parsed["question_bytes"], rcode=3)
        self.assertTrue(response[2] & 0x80)
        self.assertEqual(response[3] & 0x0F, 3)
        self.assertEqual(wire.rcode(response), 3)

    def test_echoes_question(self):
        query = wire.build_query(9, "a.example", 1)
        parsed = wire.parse_query(query)
        response = wire.build_response(parsed["id"], parsed["flags"],
                                       parsed["question_bytes"])
        self.assertIn(wire.encode_name("a.example"), response)

    def test_set_id_keeps_the_rest(self):
        payload = b"\x00\x01\x84\x00" + b"\x00" * 8
        changed = wire.set_id(payload, 0xBEEF)
        self.assertEqual(changed[:2], b"\xbe\xef")
        self.assertEqual(changed[2:], payload[2:])

    def test_truncation_bit(self):
        query = bytearray(wire.build_query(1, "a.example", 1))
        query[2] |= 0x02
        self.assertTrue(wire.is_truncated(bytes(query)))
        self.assertFalse(wire.is_truncated(wire.build_query(1, "a.example", 1)))


if __name__ == "__main__":
    unittest.main()
