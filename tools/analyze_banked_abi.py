"""Static V020 ABI analysis. stdlib only; run with uv run --no-project.

Never opens a device or writes the input image. Outputs derived addresses only.
CFG discovery is conservative recursive traversal, not a full disassembler or
proof of runtime reachability. Indirect jumps are recorded and not guessed.
"""
from pathlib import Path
from collections import Counter, deque
import argparse
import csv
import hashlib
import json
import re

SHA = '1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c'
BANK_SIZE = 0x10000
# Intel MCS-51 instruction lengths, indexed by opcode. A5 is reserved.
LENGTHS = tuple(int(c) for row in (
    '1231121111111111', '3231121111111111',
    '3211221111111111', '3211221111111111',
    '2223221111111111', '2223221111111111',
    '2223221111111111', '2221232222222222',
    '2221132222222222', '3221221111111111',
    '2221122222222222', '2221333333333333',
    '2221121111111111', '2221131122222222',
    '1211121111111111', '1211121111111111',
) for c in row)


def word(data, p):
    return (data[p] << 8) | data[p + 1]


def hits(data, pattern):
    p = data.find(pattern)
    while p >= 0:
        yield p
        p = data.find(pattern, p + 1)


def selector(n):
    return bytes([0xF8, 0x74, n, 0x90, 0xFF, 0xFF, 0xF5, 0x44, 0xF0, 0xE8, 0x22])


def gate(n):
    return bytes.fromhex('e5 44 54 0f c4 c0 e0 74 26 c0 e0 c0 82 c0 83 02') + bytes([0x26, n * 16])


def inventory(data):
    for bank in range(14):
        base = bank * BANK_SIZE
        for n in range(16):
            s, g = base + 0x2600 + n * 16, base + 0x9C2 + n * 18
            assert data[s:s + 11] == selector(n), (bank, n, 'selector')
            assert data[g:g + 18] == gate(n), (bank, n, 'gate')
        assert data[base + 0xAE2:base + 0xAE8] == bytes.fromhex('ef c4 90 26 00 73')
    thunks = {}
    for p in range(0xAE8, 0x1C46, 6):
        assert data[p] == 0x90 and data[p + 3] == 0x02
        g = word(data, p + 4)
        assert 0 <= g - 0x9C2 < 16 * 18 and (g - 0x9C2) % 18 == 0
        thunks[p] = ((g - 0x9C2) // 18, word(data, p + 1))
    for bank in range(14):
        assert data[bank * BANK_SIZE:bank * BANK_SIZE + 0x2DC4] == data[:0x2DC4]
    assert len({data[bank * BANK_SIZE + 0x2DC4] for bank in range(14)}) > 1
    return thunks


def verified_jump_tables(data):
    """Recognize bounded compiler tables, followed only from reachable jump sites."""
    # 4:EC1F uses (R7-1) modulo 256 and checks <36 before multiplying by 3.
    p = 4 * BANK_SIZE + 0xEC1F
    expected = bytes.fromhex('ef 14 b4 24 00 40 03 02 f1 29 90 ec 37 75 f0 03 a4 c5 83 25 f0 c5 83 73')
    assert data[p:p+len(expected)] == expected
    entries = []
    for n in range(36):
        local = 0xEC37 + n*3
        assert data[4*BANK_SIZE+local] == 2
        entries.append((n, local, word(data,4*BANK_SIZE+local+1)))
    tables = {(4,0xEC36):entries}
    # Compiler idioms with an explicit unsigned A<count guard and an adjacent
    # table of LJMPs. Used only when traversal reaches the matching JMP site.
    pattern = re.compile(rb'\xb4(?P<count>.)\x00(?:\x50.|\x40\x03\x02..)\x90(?P<base>..)(?P<scale>\xf8\x28\x28|\x75\xf0\x03\xa4\xc5\x83\x25\xf0\xc5\x83)\x73', re.S)
    for bank in range(14):
        chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
        for match in pattern.finditer(chunk, 0x2DC4):
            count = match['count'][0]
            base = int.from_bytes(match['base'], 'big')
            site = match.end()-1
            if base != site+1 or not count or base+3*count > BANK_SIZE:
                continue
            guard = match.start()+3
            if chunk[guard] == 0x50:
                offset = chunk[guard+1]
                target = guard+2+(offset if offset < 128 else offset-256)
                if not base+3*count <= target < BANK_SIZE:
                    continue  # Rejected selectors must bypass the entire table.
            if match['scale'] == bytes.fromhex('f8 28 28') and count > 86:
                continue  # 8-bit 3*A must not wrap.
            if not all(chunk[base+3*n] == 2 for n in range(count)):
                continue
            if (bank,site) not in tables:
                tables[bank,site] = [(n,base+3*n,word(chunk,base+3*n+1)) for n in range(count)]
    return tables


def traverse(data, thunks, extra_seeds=()):
    # These are static entry candidates: vectors and linker thunk destinations.
    # The latter need not all be reachable in the running configuration.
    seeds = {(bank, p) for bank in range(14) for p in (0, 3, 0xB, 0x13, 0x1B, 0x23, 0x2B, 0x33, 0x3B, 0x43)}
    seeds.update(thunks.values())
    # Explicit caller-verified callback entries; default traversal is unchanged.
    seeds.update(extra_seeds)
    jump_tables = verified_jump_tables(data)
    pending = deque(sorted(seeds))
    decoded, edges, indirect, reserved = {}, set(), set(), set()
    while pending:
        bank, pc = pending.popleft()
        if (bank, pc) in decoded or not 0 <= bank < 14 or not 0 <= pc < BANK_SIZE:
            continue
        if pc in thunks:
            pending.append(thunks[pc])
            continue
        if 0x9C2 <= pc < 0xAE8 or 0x2600 <= pc < 0x26FB:
            continue  # ABI modeled separately, not as same-bank flow.
        p = bank * BANK_SIZE + pc
        op = data[p]
        size = LENGTHS[op]
        if pc + size > BANK_SIZE:
            continue
        decoded[bank, pc] = size
        nxt = (pc + size) & 0xFFFF
        if op == 0xA5:
            reserved.add((bank, pc))
            continue
        if op in (0x22, 0x32):
            continue
        if op == 0x73:
            if (bank,pc) in jump_tables:
                pending.extend((bank,entry) for _,entry,_ in jump_tables[bank,pc])
            else:
                indirect.add((bank, pc))
            continue
        target, kind = None, None
        if op in (0x02, 0x12):
            target = word(data, p + 1)
            kind = 'LCALL' if op == 0x12 else 'LJMP'
        elif op & 0x1F in (0x01, 0x11):
            target = (nxt & 0xF800) | ((op & 0xE0) << 3) | data[p + 1]
            kind = 'ACALL' if op & 0x1F == 0x11 else 'AJMP'
        if target is not None:
            if kind == 'LCALL' and target == 0x20D0:
                # Inline four-byte initialization literal. Helper pops the
                # return PC, copies four MOVC bytes, and jumps past them.
                pending.append((bank, (nxt + 4) & 0xFFFF))
                continue
            if kind == 'LCALL' and target == 0x210D:
                # Byte switch: (target_hi,target_lo,value)*, 00 00, default.
                pos = nxt
                for _ in range(256):
                    if pos + 4 > BANK_SIZE:
                        break
                    dst = word(data, bank * BANK_SIZE + pos)
                    if dst == 0:
                        pending.append((bank, word(data, bank * BANK_SIZE + pos + 2)))
                        break
                    pending.append((bank, dst))
                    pos += 3
                continue
            if target in thunks:
                dstbank, dstpc = thunks[target]
                edges.add((bank, pc, kind, target, dstbank, dstpc))
                pending.append((dstbank, dstpc))
            else:
                pending.append((bank, target))
            if kind in ('LCALL', 'ACALL'):
                pending.append((bank, nxt))
            continue
        if op in (0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0xD5) or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF:
            rel = data[p + size - 1]
            pending.append((bank, (nxt + (rel if rel < 128 else rel - 256)) & 0xFFFF))
            if op == 0x80:
                continue
        pending.append((bank, nxt))
    # Report conflicting instruction coverage; never silently call this perfect CFG.
    occupied, overlaps = {}, set()
    for (bank, pc), size in sorted(decoded.items()):
        for addr in range(pc, pc + size):
            key = (bank, addr)
            if key in occupied:
                overlaps.add((bank, occupied[key], pc))
            occupied[key] = pc
    return decoded, sorted(edges), sorted(indirect), sorted(reserved), sorted(overlaps)


class AbiMachine:
    """Bounded execution of the exact gate/selector opcodes, no device I/O.

    Function bodies are replaced by a simulated return, so this checks only
    the ABI stack mechanics, not arbitrary firmware or hardware timing.
    """
    def __init__(self, data, bank):
        self.data, self.bank, self.pc = data, bank, 0
        self.ram = bytearray(256)
        self.ram[0x44] = bank
        self.stack = []

    def push_address(self, addr):
        self.stack.extend((addr & 255, addr >> 8))

    def ret(self):
        hi = self.stack.pop()
        self.pc = (hi << 8) | self.stack.pop()

    def run_until(self, bank, pc):
        for _ in range(64):
            if (self.bank, self.pc) == (bank, pc):
                return
            p = self.bank * BANK_SIZE + self.pc
            op = self.data[p]
            arg = self.data[p + 1]
            self.pc += LENGTHS[op]
            if op == 0x90:
                self.ram[0x83], self.ram[0x82] = arg, self.data[p + 2]
            elif op == 0x02:
                self.pc = word(self.data, p + 1)
            elif op == 0xE5:
                self.ram[0xE0] = self.ram[arg]
            elif op == 0x54:
                self.ram[0xE0] &= arg
            elif op == 0xC4:
                a = self.ram[0xE0]
                self.ram[0xE0] = ((a << 4) | (a >> 4)) & 255
            elif op == 0xC0:
                self.stack.append(self.ram[arg])
            elif op == 0x74:
                self.ram[0xE0] = arg
            elif op == 0xF8:
                self.ram[0] = self.ram[0xE0]
            elif op == 0xF5:
                self.ram[arg] = self.ram[0xE0]
            elif op == 0xF0:
                assert self.ram[0x82] == self.ram[0x83] == 255
                self.bank = self.ram[0xE0]
                assert self.bank < 14
            elif op == 0xE8:
                self.ram[0xE0] = self.ram[0]
            elif op == 0x22:
                self.ret()
            else:
                raise AssertionError(f'Unexpected ABI opcode {op:02x} at {p:06x}')
        raise AssertionError('ABI step budget exceeded')


def verify_abi(data, thunks):
    count = 0
    for old in range(14):
        for thunk, (dest, addr) in thunks.items():
            m = AbiMachine(data, old)
            m.ram[0xE0] = 0xA7
            m.push_address(0x3456)
            m.pc = thunk
            m.run_until(dest, addr)
            assert m.stack == [0x56, 0x34, old * 16, 0x26]
            assert m.ram[0x44] == dest
            assert m.ram[0xE0] == 0x26  # gate clobbers A; selector alone preserves it
            m.ram[0xE0] = 0xAB
            m.ret()
            m.run_until(old, 0x3456)
            assert not m.stack and m.ram[0x44] == old and m.ram[0xE0] == 0xAB
            count += 1
    # Nested calls, including same-bank transitions, across every bank triple.
    for a in range(14):
        for b in range(14):
            for c in range(14):
                m = AbiMachine(data, a)
                for dest, target, retpc in ((b, 0x4567, 0x3456), (c, 0x5678, 0x4568)):
                    m.push_address(retpc)
                    m.ram[0x82], m.ram[0x83] = target & 255, target >> 8
                    m.pc = 0x9C2 + 18 * dest
                    m.run_until(dest, target)
                for old, retpc in ((b, 0x4568), (a, 0x3456)):
                    m.ret()
                    m.run_until(old, retpc)
                    assert m.ram[0x44] == old
                assert not m.stack
    return {'thunk_round_trips': count, 'nested_bank_triples': 14 ** 3}


def write_csv(path, headers, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit('Refusing an image other than verified ASUS V020')
    thunks = inventory(data)
    tests = verify_abi(data, thunks)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / 'bank-thunks.csv', ['thunk', 'logical_bank', 'destination'],
              [(f'{p:04X}', n, f'{a:04X}') for p, (n, a) in thunks.items()])
    write_csv(args.out / 'bank-call-edges.csv', ['source_physical_bank', 'site', 'kind', 'thunk', 'target_logical_bank', 'target'],
              [(b, f'{p:04X}', k, f'{t:04X}', d, f'{a:04X}') for b, p, k, t, d, a in edges])
    non_table = []
    all_hits = list(hits(data, bytes.fromhex('90 ff ff')))
    for p in all_hits:
        b, a = divmod(p, BANK_SIZE)
        if a in range(0x2603, 0x26F4, 16):
            continue
        if data[p + 3] == 0xE0:
            category = 'current-bank-read'
        elif data[p + 3:p + 6] == bytes.fromhex('12 1d 55'):
            category = 'generic-pointer-offset-FFFF-not-bank-access'
        else:
            category = 'unclassified'
        non_table.append((b, f'{a:04X}', category, (b, a) in decoded))
    write_csv(args.out / 'bank-nontable.csv', ['physical_bank', 'site', 'classification', 'cfg_boundary'], non_table)
    raw_refs, selector_refs, old_selector_refs = [], [], []
    for b in range(14):
        chunk = data[b * BANK_SIZE:(b + 1) * BANK_SIZE]
        for a in range(BANK_SIZE - 2):
            if chunk[a] not in (0x02, 0x12):
                continue
            t = word(chunk, a + 1)
            if chunk[a] == 0x12 and t in range(0x2600, 0x26F1, 16):
                selector_refs.append((b, f'{a:04X}', f'{t:04X}', (b, a) in decoded))
            if chunk[a] == 0x12 and t in range(0x2603, 0x26F4, 16):
                old_selector_refs.append((b, f'{a:04X}', f'{t:04X}'))
            if t in thunks:
                raw_refs.append((b, f'{a:04X}', 'LCALL' if chunk[a] == 0x12 else 'LJMP', f'{t:04X}', (b, a) in decoded))
    write_csv(args.out / 'bank-raw-references.csv', ['physical_bank', 'site', 'kind', 'thunk', 'cfg_boundary'], raw_refs)
    write_csv(args.out / 'bank-unresolved-indirect.csv', ['physical_bank', 'site'], [(b, f'{a:04X}') for b, a in indirect])
    write_csv(args.out / 'bank-verified-jump-tables.csv', ['physical_bank','jump_site','selector_index','entry','target'],
              [(b,f'{p:04X}',f'{value:02X}',f'{entry:04X}',f'{target:04X}')
               for (b,p),rows in verified_jump_tables(data).items() for value,entry,target in rows])
    summary = {
        'sha256': SHA, 'size': len(data), 'common_identical_prefix_end_exclusive': '2DC4',
        'thunks': len(thunks), 'thunks_by_logical_bank': dict(sorted(Counter(n for n, a in thunks.values()).items())),
        'ffff_raw_hits': len(all_hits), 'nontable_categories': dict(Counter(r[2] for r in non_table)),
        'decoded_instruction_starts': len(decoded), 'resolved_callsite_edges': len(edges),
        'raw_long_transfer_references': len(raw_refs), 'unresolved_indirect_jumps': len(indirect),
        'raw_selector_lcalls': selector_refs, 'raw_old_misaddressed_selector_lcalls': old_selector_refs,
        'reserved_opcode_sites': [(b, f'{p:04X}') for b, p in reserved],
        'overlapping_instruction_starts': [(b, f'{a:04X}', f'{c:04X}') for b, a, c in overlaps],
        'abi_checks': tests,
        'limits': 'Static entry candidates, not runtime reachability. Logical-to-physical identity assumed for target traversal. The 210D byte-switch helper, 20D0 inline literal helper and verified physical 4:EC36 table are modeled; other indirect jumps remain unresolved. Common source copies remain duplicated. Callsite edges, not recovered function boundaries.',
    }
    (args.out / 'bank-abi-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
