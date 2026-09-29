"""Bounded x86 register/object provenance for the offline SOC campaign.

Uses the campaign's PE parser. No DLL loading or process/device access.
The decoder follows explicit CFG edges, never continues through RET, and keeps
only equal facts at joins. Unknown writes kill register facts (including aliases).
This is a deliberately small intraprocedural domain, not a full x86 emulator.
"""
from collections import deque
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_JUMP
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM

UNKNOWN = ("unknown",)


def parent_reg(name):
    for full, aliases in {
        "eax": ("ax", "al", "ah"), "ebx": ("bx", "bl", "bh"),
        "ecx": ("cx", "cl", "ch"), "edx": ("dx", "dl", "dh"),
        "esi": ("si",), "edi": ("di",), "ebp": ("bp",), "esp": ("sp",),
    }.items():
        if name in aliases:
            return full
    return name


def meet(a, b):
    out = {k: v for k, v in a.items() if k in b and b[k] == v}
    # Different older pushes must not erase equal recent arguments.
    out['pushes'] = tuple(x if x == y else UNKNOWN for x, y in zip(
        a.get('pushes', (UNKNOWN,)*16), b.get('pushes', (UNKNOWN,)*16)))
    return out


class Flow:
    def __init__(self, pe, import_map=None, object_global=None, slots=None,
                 vtable=None, virtuals=None, jump_tables=None):
        self.pe = pe
        self.cs = Cs(CS_ARCH_X86, CS_MODE_32)
        self.cs.detail = True
        self.imports = import_map or {}
        self.object_global = object_global
        self.slots = slots or {}
        self.vtable = vtable
        self.virtuals = virtuals or {}
        self.jump_tables = jump_tables or {}
        self.cache = {}

    def decode(self, va):
        if va not in self.cache:
            off = self.pe.va_to_off(va)
            valid = off is not None and any(a <= off < b for _, a, b in self.pe.exec_ranges())
            self.cache[va] = next(self.cs.disasm(self.pe.data[off:off+15], va, 1), None) if valid else None
        return self.cache[va]

    def memkey(self, ins, op, state):
        m = op.mem
        if m.segment or m.index:
            return None
        if not m.base:
            return ("abs", m.disp & 0xffffffff)
        reg = ins.reg_name(m.base)
        if reg == "ebp":
            return ("frame", m.disp)
        base = state.get(reg, UNKNOWN)
        if base[0] in {"object", "vtable"}:
            return (base[0], m.disp)
        return None

    def value(self, ins, op, state):
        if op.type == X86_OP_IMM:
            return ("imm", op.imm & 0xffffffff)
        if op.type == X86_OP_REG:
            return state.get(ins.reg_name(op.reg), UNKNOWN)
        if op.type != X86_OP_MEM:
            return UNKNOWN
        key = self.memkey(ins, op, state)
        if key in state:
            return state[key]
        if key is None:
            return UNKNOWN
        kind, off = key
        if kind == "abs":
            if off in self.imports:
                return ("import", self.imports[off], off)
            if off == self.object_global:
                return ("object", off)
        if kind == "frame" and off >= 8:
            return ("argument", off)
        if kind == "object":
            if off == 0 and self.vtable:
                return ("vtable", self.vtable)
            if off in self.slots:
                return ("api", self.slots[off], off)
        if kind == "vtable" and off in self.virtuals:
            return ("method", self.virtuals[off], off)
        return UNKNOWN

    def step(self, ins, before):
        state = dict(before)
        ops, mn = ins.operands, ins.mnemonic
        events = []
        if mn == "push":
            state["pushes"] = (state.get("pushes", (UNKNOWN,)*16) + (self.value(ins, ops[0], before),))[-16:]
            return state, events
        if mn == "call":
            target = self.value(ins, ops[0], before)
            pushes = before.get("pushes", ())
            events.append({"va": ins.address, "kind": "call", "target": target,
                           "args": tuple(reversed(pushes)), "this": before.get("ecx", UNKNOWN)})
            for reg in ("eax", "ecx", "edx", "pushes"):
                state.pop(reg, None)
            if target[:2] == ("import", "LoadLibraryW") and pushes:
                state["eax"] = ("module", ins.address, pushes[-1])
            elif target[:2] == ("import", "GetProcAddress") and len(pushes) >= 2:
                module, name = pushes[-1], pushes[-2]
                if module[0] == "module" and name[0] == "imm":
                    off = self.pe.va_to_off(name[1])
                    if off is not None:
                        end = self.pe.data.find(b"\0", off, off+128)
                        raw = self.pe.data[off:end] if end >= off else b""
                        if raw and all(32 <= c < 127 for c in raw):
                            state["eax"] = ("resolved", raw.decode("ascii"), ins.address, module)
            return state, events
        # Kill every written register, including parent of an AL/AX write.
        _, written = ins.regs_access()
        for reg in written:
            state.pop(parent_reg(ins.reg_name(reg)), None)
        if mn == "mov" and len(ops) == 2:
            value = self.value(ins, ops[1], before)
            if ops[0].type == X86_OP_REG and ops[0].size == 4:
                if value != UNKNOWN:
                    state[ins.reg_name(ops[0].reg)] = value
            elif ops[0].type == X86_OP_MEM:
                key = self.memkey(ins, ops[0], before)
                if key is not None:
                    state.pop(key, None)
                    if ops[0].size == 4 and value != UNKNOWN:
                        state[key] = value
                    events.append({"va": ins.address, "kind": "store", "key": key, "value": value})
        elif mn == "xor" and len(ops) == 2 and ops[0].type == X86_OP_REG and ops[1].type == X86_OP_REG and ops[0].reg == ops[1].reg and ops[0].size == 4:
            state[ins.reg_name(ops[0].reg)] = ("imm", 0)
        elif ops and ops[0].type == X86_OP_MEM and ops[0].access & 2:
            state.pop(self.memkey(ins, ops[0], before), None)
        return state, events

    def successors(self, ins):
        if ins.mnemonic.startswith("ret") or ins.mnemonic in {"int3", "ud2", "hlt"}:
            return []
        if ins.group(CS_GRP_JUMP):
            target = ins.operands[0]
            if target.type == X86_OP_IMM:
                return [target.imm] + ([] if ins.mnemonic == "jmp" else [ins.address+ins.size])
            return self.jump_tables.get(ins.address, [])
        return [ins.address + ins.size]

    def run(self, entry, initial=None, limit=20000):
        states = {entry: dict(initial or {})}
        queue = deque([entry]); steps = 0
        while queue:
            pc = queue.popleft(); steps += 1
            if steps > limit:
                raise ValueError(f"CFG bound exceeded at {entry:08X}")
            ins = self.decode(pc)
            if ins is None:
                continue
            after, _ = self.step(ins, states[pc])
            for dest in self.successors(ins):
                if abs(dest-entry) > 0x10000:  # external tail transfer, not a fallthrough
                    continue
                merged = meet(states[dest], after) if dest in states else after
                if dest not in states or merged != states[dest]:
                    states[dest] = merged; queue.append(dest)
        # Report only final fixed-point facts, not transient optimistic facts.
        events = []
        for pc, state in sorted(states.items()):
            ins = self.decode(pc)
            if ins:
                _, ev = self.step(ins, state); events.extend(ev)
        return states, events
