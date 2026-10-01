"""Verify OSD analog/GPIO input classification and runtime word access offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Sampled(Exception):pass


class SampleMachine(Machine):
    def readx(self, address):
        # F27A's first read is after initial classification, before stability.
        if (self.bank,self.origin,address) == (2,0xF27D,0xD826):
            raise Sampled
        return super().readx(address)


def classify(adc, pin55, sfr96):
    code = (1 if pin55 == 0 else 0) | (128 if sfr96 == 0 else 0)
    for low,high,flag in ((187,196,16),(139,154,32),(43,52,8),(75,84,4)):
        if low <= adc <= high:code |= flag
    return code


def full_sampling(data, thunks):
    class Scripted(Machine):
        def __init__(self,*args,sequence):
            super().__init__(*args)
            self.sequence = sequence; self.sample_index = 0; self.delays = 0
        def readx(self,address):
            if address == 0xFF09:
                self.x[address] = self.sequence[min(self.sample_index,len(self.sequence)-1)]
                self.sample_index += 1
            return super().readx(address)
        def jump(self,target,call=False):
            if target == 0x0DAC:
                assert (self.r(6),self.r(7)) == (0,1)
                self.delays += 1
            super().jump(target,call)
    checks = 0; capped = 0
    for adc in range(256):
        sequences = [[adc,adc], [adc,(adc+1)&255], [adc,(adc+2)&255,adc]]
        if adc == 0:
            sequences.append([0]+[v for i in range(10) for v in (40+17*i,41+17*i)])
        for sequence in sequences:
            for pin55 in (0,1):
                for sfr96 in (0,1):
                    initial = classify(adc,pin55,sfr96)
                    for old in (initial,65535):
                        for flag24 in (0,1):
                            m = Scripted(data,thunks,sequence=sequence)
                            m.x[0xFE0D] = pin55; m.sbit(0x96,sfr96)
                            m.x[0xDCA2:0xDCA4] = old.to_bytes(2,'big')
                            m.x[0xDA6E] = 255; m.sbit(0x24,flag24)
                            # CAh=0 selects the delay routine's documented early
                            # return. No timer/interrupt is fabricated or timed.
                            m.sbit(0xCA,0)
                            previous = adc; reads = 1; delays = 0; count = 0
                            if initial != old:
                                def sample():
                                    nonlocal reads
                                    value = sequence[min(reads,len(sequence)-1)]
                                    reads += 1
                                    return value
                                for _ in range(10):
                                    delays += 1
                                    if abs(sample()-previous) < 2:break
                                    previous = sample(); count += 1
                                raw = classify(previous,pin55,sfr96)
                                result = 0 if raw != 0 and flag24 and raw != 1 else raw
                                final_flag24 = 0 if raw != 0 else flag24
                            else:
                                raw = result = old; final_flag24 = flag24
                            m.run(2,0xDF25,budget=20000)
                            assert (m.r(6)<<8)|m.r(7) == result
                            assert int.from_bytes(m.x[0xDCA2:0xDCA4],'big') == result
                            assert m.x[0xDA6E] == (252 if raw else 255)
                            assert m.bit(0x24) == final_flag24
                            assert (m.sample_index,m.delays) == (reads,delays)
                            if initial != old:assert m.ram[0x26] == count
                            assert {a for _,_,a in m.writes} <= {
                                0xD826,0xD827,0xD828,0xD829,0xD82A,0xD82B,
                                0xDCA2,0xDCA3,0xDA6E}
                            checks += 1
                            if count == 10:capped += 1
    return {'checks':checks,'retry_cap_cases':capped,
            'entry':'2:DF25 through E0A2',
            'cache':'DCA2:DCA3 stores returned stable/suppressed word',
            'unchanged':'If initial mask equals cache, return cache; clear DA6E bits0/1 when nonzero.',
            'changed':'Compare successive FF09 bytes, accept absolute delta<2; otherwise replace saved byte, increment counter, retry up to 10 times.',
            'accepted_sample':'Classification uses saved D828, not the just-compared FF09 byte when stability succeeds.',
            'suppression':'On changed nonzero mask: clear DA6E bits0/1; if direct bit24h set, clear it and suppress all masks except 0001.',
            'delay':'Each retry calls 0DAC -> 5:FBC3 with R6:R7=0001; tests set bit CAh=0 so actual delay returns immediately.',
            'coverage':'Every ADC byte; stable, delta1, delta2/wrap sequences; both digital levels; matching/different cache; bit24h clear/set; 10-retry cases.',
            'limits':['No physical debounce timing is measured or emulated.',
                      'Fixtures hold digital inputs constant and scratch D829..D82B remains zero as initialized.',
                      'Cache equivalence and suppression are verified byte behavior; flags and button names remain to be classified.']}


def hold_contract(data, thunks):
    class ToggleReached(Exception):pass
    class Held(Machine):
        def __init__(self,*args):
            super().__init__(*args); self.delay_calls = 0
        def jump(self,target,call=False):
            if self.bank == 2 and self.origin == 0xF375 and target == 0x15C2:
                raise ToggleReached
            if target == 0x0DAC:
                assert (self.r(6),self.r(7)) == (0,1)
                self.delay_calls += 1
            super().jump(target,call)
    # Exact caller gate, after the earlier mode/lock conditions at E346.
    for word in range(65536):
        m = Machine(data,thunks)
        m.x[0xD820:0xD822] = word.to_bytes(2,'big')
        try:m.run(2,0xE3A9,budget=9)
        except AssertionError as error:
            assert str(error).startswith('Instruction budget exceeded at')
        else:raise AssertionError('Expected hold-call boundary')
        assert (m.bank,m.pc) == (2,0xE3B6 if word == 0x0010 else 0xE3BD)
        assert not m.writes
    for old in range(256):
        m = Held(data,thunks); m.x[0xD9FD] = old
        try:m.run(2,0xF345,budget=300)
        except ToggleReached:pass
        else:raise AssertionError('Expected post-toggle call boundary')
        assert m.x[0xD9FD] == old ^ 64
        assert {a for _,_,a in m.writes} == {0xD9FD}
    counts = []
    for source in (0,3):
        for old in (0,64):
            m = Held(data,thunks)
            m.sr(6,0);m.sr(7,16)
            m.x[0xFF09] = 187; m.x[0xFE0D] = 1;m.sbit(0x96,1)
            m.x[0xDCA2:0xDCA4] = bytes((0,16))
            m.x[0xD9FD] = old; m.x[0xDCC9] = source << 4
            m.x[0xDCB7] = 3; m.sbit(0xCA,0)
            try:m.run(2,0xF2C6,budget=2000000)
            except ToggleReached:pass
            else:raise AssertionError('Expected full hold completion')
            expected_count = 2500 if source == 3 else 5000
            assert m.delay_calls == expected_count
            assert m.x[0xD9FD] == old ^ 64
            assert bytes(m.x[0xD824:0xD826]) == bytes((0,0))
            counts.append(expected_count)
    # Immediate released input aborts after the first loop pass, without toggle.
    abort = Held(data,thunks); abort.sr(6,0);abort.sr(7,16)
    abort.x[0xFF09] = 0; abort.x[0xFE0D] = 1;abort.sbit(0x96,1)
    abort.x[0xDCB7] = 3; abort.x[0xDCC9] = 0x30;abort.sbit(0xCA,0)
    abort.run(2,0xF2C6,budget=10000)
    assert abort.c == 0 and abort.x[0xD9FD] == 0
    assert abort.delay_calls == 1
    return {'caller':'2:E346 -> E3A9..E3B6, only word 0010 calls F2C6 after earlier gates',
            'caller_checks':65536,'entry':'2:F2C6',
            'count':'5000 by default; 2500 if 7:F2FC returns 3',
            'fixture_source':'DCC9 high nibble 0/3; DCB7&1F=3; DA6B=0, D9FE.bit5=0, DA0F.bit0=0',
            'loop':'Call 0DAC with argument 1, decrement BE16 D824:D825, resample DF25 and compare against original D822:D823; stop on count zero or changed input.',
            'on_zero':'2:F34F..F374 toggles D9FD.bit6, preserving all other bits; reaches call 15C2 at F375',
            'toggle_checks':256,'full_hold_checks':len(counts),'observed_delay_call_counts':counts,
            'release_abort_checks':1,
            'limits':['Post-toggle call 15C2 is a boundary; its side effects/persistence are not executed or classified here.',
                      'Counts are delay requests, not measured milliseconds; CAh=0 selects real delay early return in fixtures.',
                      'A key-lock interpretation of D9FD.bit6 is strong evidence, not a named setting or physical-button proof.',
                      'Earlier caller gates and all alternative hold-loop conditions remain to be mapped.']}


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    sampling_checks = 0
    for adc in range(256):
        for pin55 in (0,1,2,255):
            for sfr96 in (0,1):
                m = SampleMachine(data,thunks)
                m.x[0xFF09] = adc; m.x[0xFE0D] = pin55
                m.sbit(0x96,sfr96)
                try:m.run(2,0xDF25,budget=500)
                except Sampled:pass
                else:raise AssertionError('Expected before-stability boundary')
                code = classify(adc,pin55,sfr96)
                assert int.from_bytes(m.x[0xD826:0xD828],'big') == code
                assert m.x[0xD828] == adc
                assert {a for _,_,a in m.writes} == set(range(0xD826,0xD82C))
                assert {a for _,_,a in m.reads} <= {0xFF09,0xFE0D,0xD826,0xD827,0xD828}
                sampling_checks += 1
    # Getter and previous-word copy over all possible words. No peripheral reads.
    for value in range(65536):
        high,low = value >> 8,value & 255
        m = Machine(data,thunks)
        m.x[0xDC9E:0xDCA0] = bytes((high,low))
        m.run(2,0xF20F,budget=20)
        assert (m.r(6),m.r(7)) == (high,low) and not m.writes
        m.run(2,0xF264,budget=30)
        assert bytes(m.x[0xDCA0:0xDCA2]) == bytes((high,low))
        assert {a for _,_,a in m.writes} == {0xDCA0,0xDCA1}
    # Execute exact word-write boundary used after DF25, before E6B6 consumer.
    for value in range(65536):
        m = Machine(data,thunks); m.sr(6,value>>8);m.sr(7,value&255)
        try:m.run(2,0xFDBB,budget=7)
        except AssertionError as error:
            assert str(error).startswith('Instruction budget exceeded at')
        else:raise AssertionError('Expected consumer boundary')
        assert (m.bank,m.pc) == (2,0xE6B6)
        assert int.from_bytes(m.x[0xDC9E:0xDCA0],'big') == value
        assert {a for _,_,a in m.writes} == {0xDC9E,0xDC9F}
    return {'firmware_sha256':SHA,
            'full_sampling':full_sampling(data,thunks),
            'hold_contract':hold_contract(data,thunks),
            'initial_sampling':{'entry':'2:DF25','boundary':'2:DF91 -> F27A, before first D826 read at F27D',
                'reads':['FF09 -> D828','FE0D','SFR bit 96h'],
                'output':'BE16 D826:D827', 'checks':sampling_checks,
                'analog_ranges_inclusive':[
                    {'low':187,'high':196,'mask':'0010'},
                    {'low':139,'high':154,'mask':'0020'},
                    {'low':43,'high':52,'mask':'0008'},
                    {'low':75,'high':84,'mask':'0004'}],
                'digital_rules':['FE0D==0 sets 0001','SFR bit 96h==0 sets 0080'],
                'writes':'D826..D82B scratch only; no peripheral writes at initial boundary'},
            'runtime_word':{'current':'DC9E:DC9F big-endian', 'previous':'DCA0:DCA1 big-endian',
                'getter':'2:F20F -> R6:R7','getter_checks':65536,
                'previous_copy':'2:F264 copies current to previous','copy_checks':65536,
                'writer':'2:FDBB..FDC2 stores R6:R7, then calls E6B6 at FDC3',
                'writer_checks':65536,
                'writer_parent':'2:FDB0 -> F264 (history) -> DF25 (sample/stability) -> FDBB -> E6B6 -> conditionally E20F',
                'alternate_parent':'2:FE36 -> F264 -> DF25 -> FE3C same word update -> E6B6'},
            'hardware_reference':{'repository':'Kingdomwhisky/RTD-Scaler-TEST',
                'commit':'3d38340ec8518a8888fd5d8dbb181c2a7418e11c',
                'file':'Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c',
                'FF09':'MCU_FF09_ADC_A0_CONVERT_RESULT at line 268',
                'FE0D':'MCU_FE0D_PORT55_PIN_REG at line 159',
                'qualification':'Register-role corroboration; not proof of ASUS PCB/button wiring.'},
            'limits':['Initial classification checks stop before stability; full sampling fixtures separately cover the return/retry path.',
                      'ADC/GPIO values are synthetic memory/SFR fixtures; no device reads or timing proof.',
                      'Button names and polarity at the physical switch remain unassigned.',
                      'Writer/getter/copy byte contracts are exhaustive; parent control-flow conditions are not.',
                      'Next targets: E6B6/E20F navigation consumers, repeat and physical button mapping; delay clock/timer provenance.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path); p.add_argument('--out',type=Path,required=True)
    args = p.parse_args(); result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Sampling:',result['initial_sampling']['checks'],
          'getter/copy/writer:',result['runtime_word']['getter_checks'],
          result['runtime_word']['copy_checks'],result['runtime_word']['writer_checks'])
    print('Full sampling/retry cap:',result['full_sampling']['checks'],result['full_sampling']['retry_cap_cases'])
    print('Hold caller/toggle/full:',result['hold_contract']['caller_checks'],
          result['hold_contract']['toggle_checks'],result['hold_contract']['full_hold_checks'])


if __name__ == '__main__':main()
