from migen import *
from migen.genlib.fsm import *


class PulseExtender(Module):

    """Pulse Extender

    For every rising edge of signal generates pulse of given length.
    """

    def __init__(self, pulse_max_length=255):
        self.i = Signal()
        self.o = Signal()
        self.length = Signal(max=pulse_max_length)

        # # #

        counter = Signal.like(self.length)
        re = Signal()
        i_prev = Signal()
        self.sync += [
            re.eq(self.i & ~i_prev),
            i_prev.eq(self.i)
        ]
        fsm = FSM("IDLE")
        fsm.act("IDLE", 
            self.o.eq(0),
            NextValue(counter, self.length),
            If(re, NextState("PULSE")))
        fsm.act("PULSE",
            self.o.eq(1),
            If(counter == 0, NextState("IDLE")).Else(NextValue(counter, counter-1)))
        self.submodules += fsm