"""Bounded offline interpreter for data-provenance checks, not hardware emulation.

All MOVX accesses use an in-memory bytearray. Bank thunks use the ABI map.
Unsupported instructions fail; budgets prevent runaway execution. Carry is
modeled; AC/OV/parity and interrupt timing are not. Only use on checked paths
that do not consume those unmodeled flags. Explicit byte stack and call stack
are separated, so stack-inspecting runtime helpers require explicit models.
"""
from analyze_banked_abi import LENGTHS, word


class Machine:
    def __init__(self, data, thunks, fill=0):
        self.data, self.thunks = data, thunks
        self.chunks = [memoryview(data)[i*65536:(i+1)*65536] for i in range(14)]
        self.ram = bytearray(256)
        self.x = bytearray([fill])*65536
        self.stack, self.calls = [], []
        self.reads, self.writes, self.visited, self.branches, self.transfers = set(), set(), set(), set(), set()
        self.bank, self.pc = 0, 0
        self.steps = 0

    @property
    def a(self): return self.ram[0xE0]
    @a.setter
    def a(self,v): self.ram[0xE0]=v&255
    @property
    def c(self): return self.ram[0xD0]>>7
    @c.setter
    def c(self,v): self.ram[0xD0]=(self.ram[0xD0]&127)|(int(bool(v))<<7)
    @property
    def dptr(self): return (self.ram[0x83]<<8)|self.ram[0x82]
    @dptr.setter
    def dptr(self,v): self.ram[0x83],self.ram[0x82]=(v>>8)&255,v&255

    def raddr(self,n): return (self.ram[0xD0]&0x18)+n
    def r(self,n): return self.ram[self.raddr(n)]
    def sr(self,n,v): self.ram[self.raddr(n)]=v&255
    def bitaddr(self,b): return (0x20+b//8 if b<128 else b&0xF8,b&7)
    def bit(self,b):
        a,i=self.bitaddr(b)
        return (self.ram[a]>>i)&1
    def sbit(self,b,v):
        a,i=self.bitaddr(b)
        self.ram[a]=(self.ram[a]&~(1<<i))|(int(bool(v))<<i)
    def readx(self,a):
        self.reads.add((self.bank,self.origin,a))
        return self.x[a]
    def writex(self,a,v):
        self.writes.add((self.bank,self.origin,a))
        self.x[a]=v&255
    def jump(self,t,call=False):
        self.transfers.add((self.bank,self.origin,t,call))
        if call: self.calls.append((self.bank,self.pc))
        if t in self.thunks:
            self.bank,self.pc=self.thunks[t]
        else: self.pc=t

    def run(self,bank,pc,budget=100000):
        self.bank,self.pc=bank,pc
        for _ in range(budget):
            self.steps+=1
            self.origin=self.pc
            self.visited.add((self.bank,self.pc))
            chunk=self.chunks[self.bank]
            op=chunk[self.pc]; n=LENGTHS[op]
            args=chunk[self.pc+1:self.pc+n]
            x=args[0] if args else 0; y=args[1] if len(args)>1 else 0
            self.pc=(self.pc+n)&65535
            def branch(cond,v):
                self.branches.add((self.bank,self.origin,bool(cond)))
                if cond: self.pc=(self.pc+(v if v<128 else v-256))&65535
            if op==0: pass
            elif op in (0x22,0x32):
                if not self.calls: return self.r(7)
                self.bank,self.pc=self.calls.pop()
            elif op in (2,0x12) or op&31 in (1,17):
                t=word(chunk,self.origin+1) if op in (2,0x12) else (self.pc&0xF800)|((op&0xE0)<<3)|x
                call=op==0x12 or op&31==17
                if call and t==0x20D0:
                    for j in range(4): self.writex((self.dptr+j)&65535,chunk[self.pc+j])
                    self.dptr+=4; self.pc+=4
                elif call and t==0x210D:
                    pos=self.pc
                    for _ in range(256):
                        dst=word(chunk,pos)
                        if not dst: self.pc=word(chunk,pos+2); break
                        if chunk[pos+2]==self.a: self.pc=dst; break
                        pos+=3
                    else: raise AssertionError('Unterminated byte switch')
                else: self.jump(t,call)
            elif op in (0x10,0x20,0x30):
                cond=self.bit(x)
                if op==0x30: cond=not cond
                if op==0x10 and cond: self.sbit(x,0)
                branch(cond,y)
            elif op in (0x40,0x50,0x60,0x70,0x80):
                branch({0x40:self.c,0x50:not self.c,0x60:self.a==0,0x70:self.a!=0,0x80:True}[op],x)
            elif op==0x90: self.dptr=(x<<8)|y
            elif op==0xA3: self.dptr+=1
            elif op==0xE0: self.a=self.readx(self.dptr)
            elif op==0xF0: self.writex(self.dptr,self.a)
            elif op==0xE4: self.a=0
            elif op==0xF4: self.a=~self.a
            elif op==0xC3: self.c=0
            elif op==0xD3: self.c=1
            elif op==0xB3: self.c=not self.c
            elif op==0x82: self.c=self.c and self.bit(x)  # ANL C,bit
            elif op==0xC4: self.a=(self.a<<4)|(self.a>>4)
            elif op in (3,0x13,0x23,0x33):
                a,c=self.a,self.c
                if op==3: self.a=(a>>1)|(a<<7)
                elif op==0x23: self.a=(a<<1)|(a>>7)
                elif op==0x13: self.a=(a>>1)|(c<<7); self.c=a&1
                else: self.a=(a<<1)|c; self.c=a>>7
            elif op in (0xA4,0x84):
                if op==0xA4:
                    v=self.a*self.ram[0xF0]; self.a=v; self.ram[0xF0]=v>>8
                else:
                    if self.ram[0xF0]==0: raise AssertionError('Division by zero')
                    q,r=divmod(self.a,self.ram[0xF0]);self.a=q;self.ram[0xF0]=r
                self.c=0
            elif op in (0x83,0x93): self.a=chunk[((self.pc if op==0x83 else self.dptr)+self.a)&65535]
            elif op==0x73: self.pc=(self.dptr+self.a)&65535
            elif op in (0xC0,0xD0):
                if op==0xC0:self.stack.append(self.ram[x])
                else:self.ram[x]=self.stack.pop()
            elif op in (0xB2,0xC2,0xD2): self.sbit(x,not self.bit(x) if op==0xB2 else op==0xD2)
            elif op in (0x92,0xA2):
                if op==0x92:self.sbit(x,self.c)
                else:self.c=self.bit(x)
            elif 0x74<=op<=0x7F:
                if op==0x74:self.a=x
                elif op==0x75:self.ram[x]=y
                elif op<0x78:self.ram[self.r(op&1)]=x
                else:self.sr(op&7,x)
            elif 0x85<=op<=0x8F:
                self.ram[y if op==0x85 else x]=self.ram[x] if op==0x85 else self.ram[self.r(op&1)] if op<0x88 else self.r(op&7)
            elif 0xA6<=op<=0xAF:
                if op<0xA8:self.ram[self.r(op&1)]=self.ram[x]
                else:self.sr(op&7,self.ram[x])
            elif 0xE5<=op<=0xEF:self.a=self.ram[x] if op==0xE5 else self.ram[self.r(op&1)] if op<0xE8 else self.r(op&7)
            elif 0xF5<=op<=0xFF:
                if op==0xF5:self.ram[x]=self.a
                elif op<0xF8:self.ram[self.r(op&1)]=self.a
                else:self.sr(op&7,self.a)
            elif 0xB4<=op<=0xBF:
                a=self.a if op<=0xB5 else self.ram[self.r(op&1)] if op<0xB8 else self.r(op&7)
                b=self.ram[x] if op==0xB5 else x
                self.c=a<b;branch(a!=b,y)
            elif op==0xD5 or 0xD8<=op<=0xDF:
                addr=x if op==0xD5 else self.raddr(op&7)
                self.ram[addr]=(self.ram[addr]-1)&255
                branch(self.ram[addr]!=0,y if op==0xD5 else x)
            elif 0xC5<=op<=0xCF:
                addr=x if op==0xC5 else self.r(op&1) if op<0xC8 else self.raddr(op&7)
                a=self.a;self.a=self.ram[addr];self.ram[addr]=a
            elif 4<=op<=15 or 0x14<=op<=0x1F:
                base=4 if op<16 else 0x14
                addr=0xE0 if op==base else x if op==base+1 else self.r(op&1) if op<base+4 else self.raddr(op&7)
                self.ram[addr]=(self.ram[addr]+(1 if op<16 else -1))&255
            elif op in (0x42,0x43,0x52,0x53,0x62,0x63):
                v=y if op&1 else self.a
                self.ram[x]=self.ram[x]|v if op<0x50 else self.ram[x]&v if op<0x60 else self.ram[x]^v
            elif any(base<=op<base+12 for base in (0x24,0x34,0x44,0x54,0x64,0x94)):
                base=next(base for base in (0x24,0x34,0x44,0x54,0x64,0x94) if base<=op<base+12)
                v=x if op==base else self.ram[x] if op==base+1 else self.ram[self.r(op&1)] if op<base+4 else self.r(op&7)
                if base in (0x24,0x34,0x94):
                    total=self.a-v-self.c if base==0x94 else self.a+v+(self.c if base==0x34 else 0)
                    self.c=total<0 if base==0x94 else total>255;self.a=total
                elif base==0x44:self.a|=v
                elif base==0x54:self.a&=v
                else:self.a^=v
            else: raise NotImplementedError(f'{self.bank}:{self.origin:04X} opcode {op:02X}')
        raise AssertionError(f'Instruction budget exceeded at {self.bank}:{self.pc:04X}')
