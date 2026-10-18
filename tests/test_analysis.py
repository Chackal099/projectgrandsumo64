import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze import constant_calls, fingerprint, text_prefix, graphics
from import_roms import validate


def pack(*ws):
    return struct.pack('>' + 'I' * len(ws), *ws)


class AnalysisTests(unittest.TestCase):
    def test_delay_slot_updates_call_arguments(self):
        calls = constant_calls(pack(0x24040001, 0x0C000100, 0x24050002), 0, 12, 0x80000000)
        self.assertEqual(calls[0]['regs'][4], 1)
        self.assertEqual(calls[0]['regs'][5], 2)
        self.assertEqual(calls[0]['target'], 0x80000400)

    def test_negative_low_half_is_sign_extended(self):
        calls = constant_calls(pack(0x3C04800D, 0x2484A350, 0x0C000100, 0), 0, 16, 0x80000000)
        self.assertEqual(calls[0]['regs'][4], 0x800CA350)

    def test_call_clobbers_registers_and_stack(self):
        b = pack(0x24040001, 0xAFA40010, 0x0C000100, 0, 0x0C000100, 0)
        calls = constant_calls(b, 0, len(b), 0x80000000)
        self.assertEqual(calls[0]['stack'][16], 1)
        self.assertNotIn(4, calls[1]['regs'])
        self.assertNotIn(16, calls[1]['stack'])

    def test_branch_join_does_not_invent_a_constant(self):
        b = pack(0x24040001, 0x10000002, 0, 0x24040002, 0x0C000100, 0)
        calls = constant_calls(b, 0, len(b), 0x80000000)
        self.assertNotIn(4, calls[0]['regs'])

    def test_relocation_fingerprint(self):
        a = pack(0x3C048001, 0x24841234, 0x0C000400, 0, 0x03E00008, 0)
        b = pack(0x3C04800A, 0x24845678, 0x0C001000, 0, 0x03E00008, 0)
        self.assertEqual(fingerprint(a, 0x80000400), fingerprint(b, 0x80010400))

    def test_fingerprint_keeps_logic_constants(self):
        a = pack(0x24040001, 0x03E00008, 0)
        b = pack(0x24040002, 0x03E00008, 0)
        self.assertNotEqual(fingerprint(a, 0x80000000), fingerprint(b, 0x80000000))

    def test_rsp_not_classified_as_cpu(self):
        self.assertIsNone(text_prefix(pack(0x09000419, 0x20010FC0, 0x03E00008, 0), 0, 16))

    def test_arbitrary_data_not_code(self):
        self.assertIsNone(text_prefix(bytes(64), 0, 64))

    def test_corrupted_rom_is_rejected(self):
        original = bytes.fromhex('80371240') + bytes(12)
        expected = {'size': 16, 'sha256': hashlib.sha256(original).hexdigest()}
        validate(original, expected)
        with self.assertRaises(ValueError):
            validate(original[:-1] + b'X', expected)

    def test_transfer_bits_are_distinct_from_render_bits(self):
        # CI16 transfer into TMEM, followed by a CI4 render tile.
        b = bytes(0x1000) + pack(0xFD50001F, 0x01000000, 0xF5501000, 0x07000000,
                                  0xE6000000, 0, 0xF3000000, 0x0707F200,
                                  0xE7000000, 0, 0xF5400400, 0,
                                  0xF2000000, 0x0007C07C) + bytes(160)
        result = graphics(b)
        self.assertEqual(result[0]['load_bits'], 16)
        self.assertEqual(result[0]['render_tiles'][0]['bits'], 4)
        self.assertEqual(result[0]['tile_bounds'][0]['width'], 32)

    def test_graphics_chain_stops_at_next_texture(self):
        # A palette image command must not borrow a later image's LoadBlock.
        b = bytes(0x1000) + pack(0xFD100000, 0x01000000, 0xF5100000, 0x07000000,
                                  0xFD500000, 0x01000800, 0xF5500000, 0x07000000,
                                  0xE6000000, 0, 0xF3000000, 0x0707F200,
                                  0xE7000000, 0, 0xF5400400, 0) + bytes(160)
        self.assertFalse(any(x['rom'] == 0x1000 for x in graphics(b)))


if __name__ == '__main__':
    unittest.main()
