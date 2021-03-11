from migen import *
from migen.genlib.misc import WaitTimer
from migen.genlib.fsm import FSM


class DacSpi(Module):

    def __init__(self, sclk, mosi, ncs, value=0x00999a, div=10, por_time=10):
        fsm = FSM("INIT")
        self.submodules += [fsm]

        data = Signal(24)
        counter = Signal(24, reset=23)
        por_counter = Signal(max=por_time, reset=por_time)
        half_bit_counter = Signal(max=div//2)

        self.comb += [mosi.eq(data[-1])]      

        fsm.act("INIT",
            NextValue(por_counter, por_counter-1),
            
            NextValue(ncs, 1),
            NextValue(sclk, 0),
            NextValue(data, value),

            If(por_counter == 0, 
                NextState("SYNC"),
                NextValue(half_bit_counter, div//2),
                NextValue(ncs, 0))
        )

        fsm.act("SYNC",
            NextValue(half_bit_counter, half_bit_counter-1),

            NextValue(ncs, 0),
            NextValue(sclk, 0),
            NextValue(data, value),

            If(half_bit_counter == 0, 
                NextState("SCLKH"),
                NextValue(half_bit_counter, div//2),
                NextValue(counter, 23))
        )

        fsm.act("SCLKH",
            NextValue(half_bit_counter, half_bit_counter-1),

            NextValue(ncs, 0),
            NextValue(sclk, 1),

            If(half_bit_counter == 0, 
                NextState("SCLKL"),
                NextValue(half_bit_counter, div//2)),
        )

        fsm.act("SCLKL",
            NextValue(half_bit_counter, half_bit_counter-1),

            NextValue(ncs, 0),
            NextValue(sclk, 0),

            If(half_bit_counter == 0, 
                If(counter == 0, NextState("IDLE"))
                .Else(
                    NextValue(counter, counter-1),
                    NextState("SCLKH"),
                    NextValue(half_bit_counter, div//2),
                    NextValue(data, data << 1)))
        )

        fsm.act("IDLE",            
            NextValue(ncs, 1),
            NextValue(sclk, 0)
        )


def tb(dut):
    for i in range(1000):
        yield

if __name__ == "__main__":
    sclk = Signal()
    ncs = Signal()
    mosi = Signal()

    dut = DacSpi(sclk, mosi, ncs)
    run_simulation(dut, tb(dut), vcd_name="dacspi_sim.vcd")