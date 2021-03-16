from artiq.language.core import syscall, kernel
from artiq.language.types import TBool, TInt32, TNone
from artiq.coredevice.exceptions import I2CError
from artiq.coredevice.i2c import *


class PCA9547:
    """Driver for the PCA9547 I2C bus switch.

    I2C transactions not real-time, and are performed by the CPU without
    involving RTIO.
    """
    def __init__(self, dmgr, busno=0, address=0xe0, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def set(self, channel):
        """Select given channel.

        :param channel: Channel to be selected
        """
        i2c_write_byte(self.busno, self.address, (channel & 0b111) | (1 << 3))

    @kernel
    def readback(self):
        return i2c_read_byte(self.busno, self.address)
