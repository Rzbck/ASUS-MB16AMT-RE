"""Verify bounded language-menu entry contracts and refresh geometry offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Boundary(Exception):pass


class Entry(Machine):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.boundary = None
    def jump(self,target,call=False):
        site = (self.bank,self.origin,target)
        if site in ((9,0xF566,0x19E8),(9,0xF56B,0x19EE),
                    (10,0xD396,0xBAB5),(10,0xD64B,0xF85D),
                    (10,0xC436,0xEBCD),(10,0xCEC6,0xF142)):
            self.boundary = site
            raise Boundary
        super().jump(target,call)
class History(Entry):
    def writex(self,address,value):
        super().writex(address,value)
        if (self.bank,self.origin,address) == (10,0xBEA4,0xDA6B):
            self.boundary = (10,0xBEA4,0xDA6B)
            raise Boundary


def stopped(m,bank,pc,budget=1000):
    try:m.run(bank,pc,budget=budget)
    except Boundary:pass
    else:raise AssertionError('Expected explicit call boundary')


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    assert thunks[0x19EE] == (10,0xD370)
    assert thunks[0x19DC] == (10,0xCA2A)
    pointer = 9*65536+0x8FAF+12*0x32
    assert data[pointer] == 255 and int.from_bytes(data[pointer+1:pointer+3],'big') == 0xF550
    caller_checks = 0
    for language in range(256):
        for state in (0,7):
            m = Entry(data,thunks);m.x[0xDA6B] = 0x32
            m.x[0xDA03] = language;m.x[0xDA83] = state
            stopped(m,9,0xF550)
            assert m.boundary == (9,0xF566,0x19E8)
            assert (m.r(3),m.r(7),m.r(5)) == (4,0x28,2)
            assert m.x[0xDA6B] == 0x32 and m.x[0xDA03] == language
            n = Entry(data,thunks);stopped(n,9,0xF569)
            assert n.boundary == (9,0xF56B,0x19EE) and n.r(7) == 0x56
            tail = Machine(data,thunks);tail.x[0xDA03] = language
            tail.x[0xDA48:0xDA4A] = b'\xA5\xA5'
            tail.run(9,0xF578,budget=50)
            assert bytes(tail.x[0xDA48:0xDA4A]) == bytes((0,language&63))
            assert {a for _,_,a in tail.writes} == {0xDA48,0xDA49}
            caller_checks += 1
    prologue_checks = 0
    for previous in range(256):
        for flags in range(256):
            m = Entry(data,thunks);m.sr(7,0x56)
            m.x[0xDA6B] = previous;m.x[0xDA68] = flags;m.sbit(3,1)
            m.x[0xD825:0xD82E] = b'\xA5'*9
            stopped(m,10,0xD370)
            assert m.x[0xD824] == 0x56
            assert bytes(m.x[0xD825:0xD82E]) == b'\0'*9
            assert m.x[0xDA68] == ((flags|64) if previous == 0x56 else (flags&191))
            assert not m.bit(3) and m.x[0xDA6B] == previous
            assert {a for _,_,a in m.writes} == set(range(0xD824,0xD82E))|{0xDA68}
            prologue_checks += 1
    class Gate(Entry):
        def jump(self,target,call=False):
            if (self.bank,self.origin,target) == (10,0xD396,0xBAB5):
                Machine.jump(self,target,call)
            else:super().jump(target,call)
    gate_checks = 0
    for previous in (0x32,0x56):
        for flags in range(256):
            for carry in (0,1):
                m = Gate(data,thunks);m.sr(7,0x56);m.c = carry
                m.x[0xDA6B] = previous;m.x[0xDA68] = flags
                try:m.run(10,0xD370,budget=500)
                except Boundary:pass
                if previous == 0x32:
                    assert m.boundary == (10,0xD64B,0xF85D)
                    assert m.r(7) == 0x1A and m.bit(4)
                else:assert m.boundary is None and (10,0xD686) in m.visited
                assert m.x[0xDA6B] == previous
                gate_checks += 1
    history_checks = 0
    for previous in range(256):
        for carry in (0,1):
            m = History(data,thunks);m.x[0xD824] = 0x56;m.c = carry
            m.x[0xDA6B] = previous;m.x[0xD82E:0xD833] = b'\xA5'*5
            stopped(m,10,0xD735)
            assert m.boundary == (10,0xBEA4,0xDA6B)
            assert m.x[0xDA6B] == 0x56
            assert bytes(m.x[0xD82E:0xD833]) == bytes((1,previous,0,0,0))
            assert m.r(7) == 0x56
            assert {a for _,_,a in m.writes} == set(range(0xD82E,0xD833))|{0xDA6B}
            history_checks += 1
    for carry in (0,1):
        m = Entry(data,thunks);m.x[0xD824] = 0x56;m.c = carry
        m.x[0xDA6B] = 0x32
        stopped(m,10,0xD735)
        assert m.boundary == (10,0xC436,0xEBCD) and m.r(7) == 16
        assert m.x[0xDA6B] == 0x56
        assert bytes(m.x[0xD82E:0xD833]) == bytes((1,0x32,0,0,0))
    geometry_checks = 0;geometry = []
    for index in range(21):
        group,local = divmod(index,8)
        first = 12*(25+13*group)
        extent = 14 if group == 2 else 13
        second = 72+36*local
        expected = (first,second,first+12*extent-(group != 2),second+36)
        for carry in (0,1):
            for fill in (0,0x55,0xAA,0xFF):
                m = Entry(data,thunks,fill=fill);m.c = carry
                m.x[0xD833] = 0x56;m.x[0xD834] = index
                stopped(m,10,0xCD7E)
                actual = tuple(int.from_bytes(m.x[a:a+2],'big') for a in range(0xD83C,0xD844,2))
                assert actual == expected, (index,carry,fill,actual,expected)
                assert m.boundary == (10,0xCEC6,0xF142) and m.r(7) == 6
                assert m.x[0xD834] == local and m.x[0xD836] == 25+13*group
                assert m.x[0xD837] == extent
                assert bytes(m.x[0xD844:0xD846]) == bytes((0,7)) and m.bit(5)
                assert {a for _,_,a in m.writes} <= {0xD834,0xD836,0xD837}|set(range(0xD83C,0xD846))
                assert not m.calls and not m.stack
                geometry_checks += 1
        geometry.append({'index':index,'group':group,'local':local,'D83C_D83E_D840_D842':list(expected)})
    return {'firmware_sha256':SHA,'caller_checks':caller_checks,
            'entry_prologue_checks':prologue_checks,'entry_guard_checks':gate_checks,
            'history_checks':history_checks,'row32_history_route_checks':2,'geometry_checks':geometry_checks,
            'caller':'Row32 command0 ->9:F550: pre-drawing19E8 gets R3=4/R7=28/R5=2; F569 passes R7=56 to19EE ->10:D370. F578 tail seeds DA48:DA49 from DA03&3F.',
            'entry':'10:D370 saves target to D824, clears direct bit03 and D825..D82D; DA68.bit6 is set iff previous DA6B equals target, otherwise cleared. Target56/new row reaches D64B drawing call; same row returns D686.',
            'history':'10:D735 ->BE8C receives R7=1/R5=D824. Prefix BE8C..BEA4 writes DA6B=56 and D82E..D832=01,previous-setting,00,00,00. Two separate row32 fixtures continue to EBCD at C436 with R7=10h; arbitrary previous-row drawing is excluded.',
            'geometry':'10:CA2A row56 branch ->CD7E..CEC6 uses selected index in D834, splits0..7/8..15/16..20 and prepares four BE16 fields D83C/D83E/D840/D842, D844:D845=00:07 and direct bit05=1 before F142 with R7=6.',
            'formula':'g=index//8, n=index%8: (12*(25+13*g),72+36*n,780 if g==2 else12*(25+13*g)+155,108+36*n). Third group omits the minus1 used by the first two.',
            'indices':geometry,
            'limits':['All execution is offline; no monitor/storage command.',
                      'Entry checks compose separate caller/prologue/history/seed contracts; full entry drawing between them is not executed.',
                      'Geometry fixtures start at CD7E after refresh setup and stop before F142; physical dimensions, orientation and final hardware coordinates remain unproved.',
                      'Language names, full apply drawing and other dirty-save leaves remain open.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path);p.add_argument('--out',type=Path,required=True)
    args = p.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Entry/prologue/guard/history/geometry checks:',*(result[k] for k in
          ('caller_checks','entry_prologue_checks','entry_guard_checks','history_checks','geometry_checks')))


if __name__ == '__main__':main()
