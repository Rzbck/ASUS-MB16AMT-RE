"""Check ANL C,bit truth table, all bit addresses and RAM preservation."""
from emulate_mcs51 import Machine


def main():
    checks = 0
    for address in range(256):
        for carry in (0,1):
            for operand in (0,1):
                data = bytearray(0xE0000)
                data[0x3000:0x3003] = bytes((0x82,address,0x22))
                m = Machine(data,{})
                m.ram[:] = bytes((0xA5,))*256
                m.c = carry;m.sbit(address,operand)
                # OperandD7 aliases carry, so use the actual initial snapshot.
                initial = bytes(m.ram)
                byte = 0x20+address//8 if address<128 else address&0xF8
                source = (initial[byte]>>(address&7))&1
                expected = bytearray(initial)
                expected[0xD0] = (initial[0xD0]&0x7F)|(((initial[0xD0]>>7)&source)<<7)
                m.run(0,0x3000,budget=3)
                assert m.ram == expected and m.steps == 2
                assert not m.reads and not m.writes and not m.calls and not m.stack
                checks += 1
    print('MCS-51 ANL C,bit truth/address/preservation checks:',checks)


if __name__ == '__main__':main()
