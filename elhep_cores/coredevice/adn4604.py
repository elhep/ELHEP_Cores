from artiq.language.core import syscall, kernel
from artiq.language.types import TBool, TInt32, TNone
from artiq.coredevice.exceptions import I2CError
from artiq.coredevice.i2c import *


class Adn4604:

    def __init__(self, dmgr, busno=0, address=0x90, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def write_reg(self, address, value):
        i2c_write_byte(self.busno, self.address, address, value)

    @kernel
    def read_reg(self, address):
        return i2c_read_byte(self.busno, self.address, address)

    @kernel
    def update(self):
        self.write_reg(0x80, 1)

    @kernel
    def connect_input_to_output(self, input, output, xpt_map=0):
        assert xpt_map in [0, 1]
        assert 0 <= input <= 15
        assert 0 <= output <= 15

        adddress = 0x90 + output // 2 + xpt_map * 8
        oldval = self.read_reg(address)
        if output % 2 == 1:
            oldval &= 0b00001111
            oldval |= input << 4
        else:
            oldval &= 0b11110000
            oldval |= input
        self.write_reg(address, oldval)

        self.update()

    @kernel
    def select_xpt_map(self, xpt_map):
        assert xpt_map in [0, 1]
        self.write_reg(0x81, xpt_map)
    


