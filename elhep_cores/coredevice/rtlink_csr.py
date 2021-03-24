from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.units import ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.types import TInt32
import csv


class RtlinkCsr:

    class Reg:

        def __init__(self, channel, address, length, core):
            self.channel = channel
            self.address = address
            self.length = length
            self.core = core

        @kernel
        def write_rt(self, data):
            rtio_output((self.channel << 8) | self.address << 1 | 1, data & ((0x1 << self.length)-1))
            delay_mu(1)

        @kernel
        def write(self, data):
            self.core.break_realtime()
            self.write_rt(data)

        @kernel
        def read_rt(self) -> TInt32:
            rtio_output((self.channel << 8) | self.address << 1 | 0, 0)
            delay_mu(1)
            return rtio_input_data(self.channel)

        @kernel
        def read(self) -> TInt32:
            self.core.break_realtime()
            return self.read_rt()

    def __init__(self, dmgr, channel, regs, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        for address, reg in enumerate(regs):
            new_reg = RtlinkCsr.Reg(
                channel=self.channel, 
                address=address,
                length=reg[1],
                core=self.core)
            setattr(self, reg[0], new_reg)
        
