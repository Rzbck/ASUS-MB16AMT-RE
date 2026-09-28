"""Small static MCS-51 decoder, sharing instruction lengths with ABI mapper.

No device access. Addresses are code offsets unless explicitly called XDATA.
"""
from analyze_banked_abi import LENGTHS, word


def decode(data, pc):
    op = data[pc]
    n = LENGTHS[op]
    args = list(data[pc + 1:pc + n])
    x = args[0] if args else 0
    y = args[1] if len(args) > 1 else 0
    direct = lambda v: f'{v:02X}h'
    imm = lambda v: f'#{v:02X}h'
    rel = lambda v: f'{(pc+n+(v if v<128 else v-256))&65535:04X}'
    rn = f'R{op&7}'
    ri = f'@R{op&1}'
    if op & 31 in (1, 17):
        return ('ACALL' if op & 31 == 17 else 'AJMP') + f' {((pc+n)&0xF800)|((op&0xE0)<<3)|x:04X}'
    fixed = {0:'NOP', 3:'RR A', 0x13:'RRC A', 0x22:'RET', 0x23:'RL A', 0x32:'RETI',
             0x33:'RLC A', 0x73:'JMP @A+DPTR', 0x83:'MOVC A,@A+PC', 0x84:'DIV AB',
             0x93:'MOVC A,@A+DPTR', 0xA3:'INC DPTR', 0xA4:'MUL AB', 0xA5:'RESERVED',
             0xB3:'CPL C', 0xC3:'CLR C', 0xC4:'SWAP A', 0xD3:'SETB C', 0xD4:'DA A',
             0xE0:'MOVX A,@DPTR', 0xE4:'CLR A', 0xF0:'MOVX @DPTR,A', 0xF4:'CPL A'}
    if op in fixed:
        return fixed[op]
    if op in (2, 0x12):
        return f'{"LJMP" if op==2 else "LCALL"} {(x<<8)|y:04X}'
    if op in (0x10, 0x20, 0x30):
        return f'{ {0x10:"JBC",0x20:"JB",0x30:"JNB"}[op]} {direct(x)},{rel(y)}'
    if op in (0x40,0x50,0x60,0x70,0x80):
        return f'{ {0x40:"JC",0x50:"JNC",0x60:"JZ",0x70:"JNZ",0x80:"SJMP"}[op]} {rel(x)}'
    for base, name in ((4,'INC'),(0x14,'DEC')):
        if base<=op<base+12:
            arg = 'A' if op==base else direct(x) if op==base+1 else ri if op<base+4 else rn
            return f'{name} {arg}'
    for base,name in ((0x24,'ADD'),(0x34,'ADDC'),(0x44,'ORL'),(0x54,'ANL'),(0x64,'XRL'),(0x94,'SUBB')):
        if base<=op<base+12:
            arg=imm(x) if op==base else direct(x) if op==base+1 else ri if op<base+4 else rn
            return f'{name} A,{arg}'
    if op in (0x42,0x52,0x62):
        return f'{ {0x42:"ORL",0x52:"ANL",0x62:"XRL"}[op]} {direct(x)},A'
    if op in (0x43,0x53,0x63):
        return f'{ {0x43:"ORL",0x53:"ANL",0x63:"XRL"}[op]} {direct(x)},{imm(y)}'
    if op in (0x72,0x82,0xA0,0xB0):
        return f'{"ORL" if op in (0x72,0xA0) else "ANL"} C,{"/" if op>=0xA0 else ""}{direct(x)}'
    if op==0x90:
        return f'MOV DPTR,#{(x<<8)|y:04X}h'
    if op in (0x92,0xA2):
        return f'MOV {direct(x)},C' if op==0x92 else f'MOV C,{direct(x)}'
    if 0x74<=op<=0x7F:
        dest='A' if op==0x74 else direct(x) if op==0x75 else ri if op<0x78 else rn
        return f'MOV {dest},{imm(y if op==0x75 else x)}'
    if 0x85<=op<=0x8F:
        src=direct(x) if op==0x85 else ri if op<0x88 else rn
        return f'MOV {direct(y if op==0x85 else x)},{src}'
    if 0xA6<=op<=0xAF:
        return f'MOV {ri if op<0xA8 else rn},{direct(x)}'
    if 0xB4<=op<=0xBF:
        src='A' if op<=0xB5 else ri if op<0xB8 else rn
        return f'CJNE {src},{direct(x) if op==0xB5 else imm(x)},{rel(y)}'
    if op in (0xB2,0xC2,0xD2,0xC0,0xD0):
        return f'{ {0xB2:"CPL",0xC2:"CLR",0xD2:"SETB",0xC0:"PUSH",0xD0:"POP"}[op]} {direct(x)}'
    if 0xC5<=op<=0xCF:
        return f'XCH A,{direct(x) if op==0xC5 else ri if op<0xC8 else rn}'
    if op==0xD5 or 0xD8<=op<=0xDF:
        return f'DJNZ {direct(x) if op==0xD5 else rn},{rel(y if op==0xD5 else x)}'
    if op in (0xD6,0xD7):
        return f'XCHD A,{ri}'
    if op in (0xE2,0xE3,0xF2,0xF3):
        return f'MOVX A,{ri}' if op<0xF0 else f'MOVX {ri},A'
    if 0xE5<=op<=0xEF:
        return f'MOV A,{direct(x) if op==0xE5 else ri if op<0xE8 else rn}'
    if 0xF5<=op<=0xFF:
        return f'MOV {direct(x) if op==0xF5 else ri if op<0xF8 else rn},A'
    raise ValueError(f'Unhandled opcode {op:02X}')


def listing(data, bank, lo, hi, thunks=None):
    chunk = data[bank*65536:(bank+1)*65536]
    pc = lo
    lines=[]
    while pc<hi:
        text=decode(chunk,pc)
        if chunk[pc] in (2,0x12) and thunks and word(chunk,pc+1) in thunks:
            b,a=thunks[word(chunk,pc+1)]
            text+=f' ; -> {b}:{a:04X}'
        lines.append(f'{bank}:{pc:04X}  {text}')
        pc+=LENGTHS[chunk[pc]]
    return '\n'.join(lines)
