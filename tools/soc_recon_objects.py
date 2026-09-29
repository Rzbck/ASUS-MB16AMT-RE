"""Verified object-relative resolver and call ABI phase for the SOC campaign.

Profiles select analysis roots, not precomputed results: the PE fingerprint,
imports, CFG register provenance, resolver stores, calls and stack cleanup are
checked from local bytes. Reports contain derived metadata only.
"""
from pathlib import Path
import hashlib
import struct

from soc_recon_deep import imports, find_all
from x86_object_flow import Flow

PLUGIN_SHA = "13242a1dc8f1d263cb4235ae50b6409855e259fbf3fe894bc06584389a16334c"
WINCOMM_SHA = "d237f4fbe3ab3acfc4170558785b422aeaea055627522510105f5517b0d78739"
OBJECT_GLOBAL = 0x1020BCFC
VTABLE = 0x101D8EA4
RESOLVER = 0x10003DE0


def table(pe, va, count):
    off = pe.va_to_off(va)
    if off is None or off + count*4 > len(pe.data):
        raise ValueError(f"Unmapped table {va:08X}")
    return list(struct.unpack_from(f"<{count}I", pe.data, off))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cleanup(flow, call):
    ins = flow.decode(call)
    # ReadRegsEx reloads saved values before cleaning its four arguments.
    for _ in range(8):
        ins = flow.decode(ins.address + ins.size)
        if not ins or ins.mnemonic in {"call", "ret", "jmp"}:
            break
        if ins.mnemonic == "add" and ins.op_str.startswith("esp, "):
            return ins.operands[1].imm
    return None


def analyze_objects(pe):
    sha = hashlib.sha256(pe.data).hexdigest()
    if sha != PLUGIN_SHA:
        return None
    imp = {va: name for dll, name, rva, va in imports(pe) if dll.lower() == "kernel32.dll"}
    flow = Flow(pe, imp, object_global=OBJECT_GLOBAL)
    states, events = flow.run(RESOLVER)
    rows = []
    for e in events:
        if e['kind'] == 'store' and e['key'][0] == 'object' and e['value'][0] == 'resolved':
            _, name, call_va, module = e['value']
            rows.append(dict(name=name, offset=e['key'][1], resolver_call_va=call_va,
                             store_va=e['va'], module_load_va=module[1]))
    slots = {r['offset']: r['name'] for r in rows}
    for off, name in {0xBC:'ReadRegEx', 0xC4:'ReadRegsEx', 0xA4:'ReadReg',
                      0xAC:'ReadRegs', 0xD4:'ReadSysDevice', 0xDC:'ReadWordSysDevice',
                      0x110:'NativeRead', 0x74:'I2CReadEx'}.items():
        require(slots.get(off) == name, f"Resolver dataflow did not prove {name} +{off:X}")
    require(len(rows) == 119 and len(slots) == 118, "Resolver table changed/incomplete")
    virtuals = dict(enumerate(table(pe, VTABLE, 10)))
    virtuals = {n*4: va for n, va in virtuals.items()}
    require(virtuals[12] == 0x10003530, 'ReadRegEx vtable binding changed')
    targets = table(pe, 0x1001F968, 27)
    require(targets[0x15] == 0x1001F705, 'ReadRegsEx command dispatch changed')
    flow = Flow(pe, imp, object_global=OBJECT_GLOBAL, slots=slots, vtable=VTABLE,
                virtuals=virtuals, jump_tables={0x1001F23D: targets})
    wrapper_states, wrapper_events = flow.run(virtuals[12], {'ecx':('object', OBJECT_GLOBAL)})
    wrapper_calls = [e for e in wrapper_events if e['kind']=='call' and e['target'][:2]==('api','ReadRegEx')]
    require(len(wrapper_calls)==1, 'ReadRegEx wrapper call missing')
    require(wrapper_calls[0]['args'][:2] == (('argument',8),('argument',12)), 'Wrapper arguments changed')
    require(cleanup(flow,wrapper_calls[0]['va'])==8, 'cdecl two-argument cleanup missing')
    # The indirect call is shared with command 0x19 / ReadMcuRegs. Restrict
    # dispatch to command 0x15 for this proof; do not merge unlike callees.
    command_flow = Flow(pe, imp, object_global=OBJECT_GLOBAL, slots=slots,
        vtable=VTABLE, virtuals=virtuals,
        jump_tables={0x1001F23D: [targets[0x15]]})
    dispatch_states, dispatch_events = command_flow.run(0x1001F200)
    read_many = [e for e in dispatch_events if e['kind']=='call' and e['target'][:2]==('api','ReadRegsEx')]
    require(len(read_many)==1 and read_many[0]['va']==0x1001F75A, 'ReadRegsEx command-path dataflow missing')
    require(cleanup(flow,read_many[0]['va'])==16, 'cdecl four-argument cleanup missing')

    # Candidate root discovery only. Each result below must be reached by a CFG
    # decoding from that root and carry the identity loaded from OBJECT_GLOBAL.
    roots = {0x1001F200, 0x10021D70}
    for sec, a, b in pe.exec_ranges():
        for off in find_all(pe.data, struct.pack('<I',OBJECT_GLOBAL), a, b):
            start = pe.data.rfind(b'\x55\x8b\xec', max(a,off-0x4000), off)
            if start >= 0:
                roots.add(pe.off_to_va(start))
    uses = {}; incomplete = []
    for root in sorted(roots):
        try:
            rs, es = flow.run(root)
        except ValueError:
            incomplete.append(root); continue
        for e in es:
            if e['kind'] != 'call': continue
            target=e['target']
            if target[0]=='api' or (target[0]=='method' and target[1]==virtuals[12]):
                name = target[1] if target[0]=='api' else 'ReadRegEx (virtual wrapper)'
                uses[e['va']] = dict(va=e['va'], root=root, name=name,
                                      target=target, cleanup_bytes=cleanup(flow,e['va']), args=e['args'][:5])
    uses[wrapper_calls[0]['va']] = dict(va=wrapper_calls[0]['va'],root=virtuals[12],
        name='ReadRegEx',target=wrapper_calls[0]['target'],cleanup_bytes=8,args=wrapper_calls[0]['args'][:2])
    return dict(file=pe.path.name, sha256=sha, image_base=pe.image_base,
                status='CONFIRMED_OBJECT_RESOLVER_AND_ABI', object_global=OBJECT_GLOBAL,
                resolver_entry=RESOLVER, resolver_instructions=len(states),
                getprocaddress_iat=next(va for va,n in imp.items() if n=='GetProcAddress'),
                loadlibrary_iat=next(va for va,n in imp.items() if n=='LoadLibraryW'),
                slots=rows, vtable=VTABLE, virtuals=virtuals,
                command_15_call=read_many[0],
                calls=sorted(uses.values(),key=lambda x:x['va']), candidate_roots=len(roots),
                bounded_out_roots=incomplete,
                limitations=['Profile-specific static proof; no runtime execution implied.',
                    'Root discovery and unresolved indirect control flow are incomplete; zero hits is not absence.',
                    'The 0x1001F75A proof is conditioned on command 0x15; command 0x19 shares the call with ReadMcuRegs.',
                    'Unknown calls clobber volatile registers; callee-saved object aliases use the x86 ABI.',
                    'Object identity assumes the published singleton and vtable are not replaced concurrently.'])


def print_objects(report, full=False):
    print('===== OBJECT-RELATIVE RESOLVER / ABI =====')
    print(f"{report['file']} SHA256={report['sha256']}")
    print(f"CONFIRMED: resolver VA=0x{report['resolver_entry']:08X}; object=[0x{report['object_global']:08X}]")
    print(f"CONFIRMED: GetProcAddress IAT=0x{report['getprocaddress_iat']:08X}; LoadLibraryW IAT=0x{report['loadlibrary_iat']:08X}")
    print(f"CONFIRMED: {len(report['slots'])} resolutions / {len(set(r['offset'] for r in report['slots']))} object slots reconstructed by CFG dataflow")
    selected={'ReadRegEx','ReadRegsEx','ReadReg','ReadRegs','ReadSysDevice','ReadWordSysDevice','NativeRead','I2CReadEx'}
    for r in sorted(report['slots'],key=lambda x:x['offset']):
        if full or r['name'] in selected:
            print(f"  +0x{r['offset']:03X} {r['name']:<26} resolve=0x{r['resolver_call_va']:08X} store=0x{r['store_va']:08X}")
    print('CONFIRMED: ReadRegEx(address, byte* out): cdecl, two 32-bit stack slots, EAX status.')
    print('CONFIRMED: ReadRegsEx(address, count, byte* out, increment): cdecl, four stack slots.')
    print('CONFIRMED: ReadRegEx wrapper VA=0x10003530 is a thiscall method at vtable +0x0C; it calls the cdecl export.')
    print('CONFIRMED: ReadRegsEx command 0x15 at VA=0x1001F705; export call=0x1001F75A.')
    for r in report['calls']:
        if r['name'].startswith(('ReadRegEx','ReadRegsEx')):
            print(f"  object-proven use VA=0x{r['va']:08X} {r['name']} cleanup={r['cleanup_bytes']} root=0x{r['root']:08X}")
    print(f"Coverage: {report['candidate_roots']} candidate roots; {len(report['bounded_out_roots'])} exceeded the analysis bound. Not a complete call graph.")
    print('HYPOTHESIS ONLY: this register address space can expose scaler XDATA / battery state.')
