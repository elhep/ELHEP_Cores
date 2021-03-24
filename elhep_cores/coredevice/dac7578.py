from artiq.language.core import syscall, kernel
from artiq.language.types import TBool, TInt32, TNone
from artiq.coredevice.exceptions import I2CError
from artiq.coredevice.i2c import *


class DAC7578:

    def __init__(self, dmgr, address, busno=0, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def set_mu(self, ch, value):
        v0 = (value >> 4) & 0xFF
        v1 = (value << 4) & 0xFF
        i2c_write_many(self.busno, self.address, 0b0011 | (ch & 0xF), [v0, v1])
