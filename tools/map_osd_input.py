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
                code = (1 if pin55 == 0 else 0) | (128 if sfr96 == 0 else 0)
                for low,high,flag in ((187,196,16),(139,154,32),(43,52,8),(75,84,4)):
                    if low <= adc <= high:code |= flag
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
            'limits':['Classification checks stop before DF25 stability/retry/delay logic.',
                      'ADC/GPIO values are synthetic memory/SFR fixtures; no device reads or timing proof.',
                      'Button names and polarity at the physical switch remain unassigned.',
                      'Writer/getter/copy byte contracts are exhaustive; parent control-flow conditions are not.',
                      'Next targets: DF25 full stability and E6B6/E20F navigation consumers; DCA2:DCA3 stable-word role.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path); p.add_argument('--out',type=Path,required=True)
    args = p.parse_args(); result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Sampling:',result['initial_sampling']['checks'],
          'getter/copy/writer:',result['runtime_word']['getter_checks'],
          result['runtime_word']['copy_checks'],result['runtime_word']['writer_checks'])


if __name__ == '__main__':main()
