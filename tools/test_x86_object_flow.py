"""Synthetic CFG safety regressions; no proprietary bytes or device I/O."""
import unittest
from x86_object_flow import Flow


class Memory:
    def __init__(self, code):
        self.data = bytes.fromhex(code)

    def va_to_off(self, va):
        return va - 0x1000 if 0x1000 <= va < 0x1000 + len(self.data) else None

    def exec_ranges(self):
        return [('synthetic', 0, len(self.data))]


class FlowTests(unittest.TestCase):
    def calls(self, code, initial=None):
        _, events = Flow(Memory(code)).run(0x1000, initial)
        return [e for e in events if e['kind'] == 'call']

    def test_conflicting_branch_targets_do_not_become_proof(self):
        # jz alternate; mov eax,1; jmp call; alternate: mov eax,2; call eax
        calls = self.calls('74 07 b8 01 00 00 00 eb 05 b8 02 00 00 00 ff d0 c3')
        self.assertEqual(calls[0]['target'], ('unknown',))

    def test_equal_branch_targets_survive(self):
        calls = self.calls('74 07 b8 01 00 00 00 eb 05 b8 01 00 00 00 ff d0 c3')
        self.assertEqual(calls[0]['target'], ('imm', 1))

    def test_partial_write_kills_parent(self):
        calls = self.calls('b8 01 00 00 00 b0 02 ff d0 c3')
        self.assertEqual(calls[0]['target'], ('unknown',))

    def test_does_not_decode_after_return(self):
        self.assertEqual(self.calls('c3 ff d0'), [])

    def test_call_clobbers_volatile_but_preserves_abi_register(self):
        calls = self.calls('ff d7 ff d0 ff d6 c3',
            {'eax':('api','volatile'), 'esi':('api','preserved')})
        self.assertEqual(calls[1]['target'], ('unknown',))
        self.assertEqual(calls[2]['target'], ('api','preserved'))


if __name__ == '__main__':
    unittest.main()
