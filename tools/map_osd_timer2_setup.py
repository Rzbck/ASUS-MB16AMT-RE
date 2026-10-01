"""Verify Timer2 setup with Timer0/1 stopped, entirely offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


def fixture(data,thunks,mode,register,old=0):
    m = Machine(data,thunks);m.sr(7,mode);m.x[0xFFED] = register;m.x[0xD928] = old
    m.run(5,0xCA9B,budget=400)
    low,high,reload_low,reload_high = ((0x73,0xE3,0x73,0xE3) if mode == 1 else
        (0xE2,0xF6,0xE2,0xF6) if mode == 2 else
        (0xD3,0,0xE2,0xF6) if mode == 4 else (0x56,0xFB,0x56,0xFB))
    assert tuple(m.ram[a] for a in (0xCC,0xCD,0xCA,0xCB)) == (low,high,reload_low,reload_high)
    assert m.bit(0xAD) == m.bit(0xCA) == 1 and m.bit(0xCF) == m.bit(0x1E) == 0
    assert m.x[0xD928] == (1 if mode == 1 else 3 if (register&0x3C)>>2 == 1 else 2) if mode in (1,2) else m.x[0xD928] == old
    assert {a for _,_,a in m.writes} <= set(range(0xD822,0xD828))|{0xD928}
    assert not m.stack and not m.calls


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);checks = history = 0
    assert thunks[0x0D16] == (5,0xCA9B)
    assert data[0x63BF:0x63C3] == bytes.fromhex('FF 12 0D 16')
    for mode in range(256):
        for register in range(256):
            fixture(data,thunks,mode,register);checks += 1
    for old in range(256):
        for mode in (1,2):
            for register in (0,4):
                fixture(data,thunks,mode,register,old);history += 1
    return {'firmware_sha256':SHA,'mode_register_checks':checks,'old_mode_checks':history,
            'entry':'5:CA9B;0:63BF MOV R7,A after0:639C CLRA ->0:63C0 call0D16 suppliesmode0.',
            'SFR_contract':'CC:CD receivecount low:high; CA:CB receivereload low:high. ClearET2/TR2/TF2,writebytes,clearbit1E,enableET2/TR2. Alloriginalinstructions execute.',
            'counts':[{'mode':'01','count':'E373','reload':'E373'},
                      {'mode':'02','count':'F6E2','reload':'F6E2'},
                      {'mode':'04','count':'00D3','reload':'F6E2'},
                      {'mode':'other including00','count':'FB56','reload':'FB56'}],
            'history':'D928 becomes1 for mode1; mode2 becomes3 iffFFED bits5..2 equal1, otherwise2. Other modes retainD928.',
            'limits':['Offline only; nohardwaretimer configured.',
                      'TR0/TR1 initiallyclear inallfixtures; their running-timer deadline conversion branches are excluded.',
                      'SFR addresses matchTimer2 register layout; physicalclock source/divider/frequency notproved.',
                      'Mode4 firstcount differsfromreload; do not assign a constanttickperiod fromreload alone.',
                      'Initialization caller prefix checked statically, not a completeMCUinitialization run.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Timer2 mode/register/history checks:',result['mode_register_checks'],result['old_mode_checks'])


if __name__ == '__main__':main()
