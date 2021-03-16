from migen import *
from migen.genlib.io import DifferentialInput
from migen.genlib.cdc import BusSynchronizer
from artiq.gateware.rtio import rtlink
from elhep_cores.cores.dsp.baseline import SignalBaseline
from functools import reduce
from operator import and_, add
from elhep_cores.cores.rtlink_csr import RtLinkCSR


def divide_chunks(l, n): 
    for i in range(0, len(l), n):  
        yield l[i:i + n] 


class TriggerGenerator(Module):

    def __init__(self, name):
        self.name = name
        self.triggers = []

    def register_trigger(self, signal, name, cd):
        self.triggers.append({
            "signal": signal,
            "label": f"{self.name}_{name}",
            "cd": cd
        })


class ExternalTriggerInput(TriggerGenerator):

    def __init__(self, pad, pad_n=None, name="external_trigger"):
        super().__init__(name)
        
        # Outputs 
        self.trigger_re = Signal()  # CD: sys
        self.trigger_fe = Signal()  # CD: sys

        self.register_trigger(self.trigger_re, "re", self.cd_sys)
        self.register_trigger(self.trigger_fe, "fe", self.cd_sys)

        # # #

        if pad_n is not None:
            external_trigger = Signal()
            self.specials += DifferentialInput(pad, pad_n, external_trigger)
        else:
            external_trigger = pad
        
        trigger_ext_d = Signal()
        trigger_ext_prev = Signal()
        self.sync += [
            trigger_ext_prev.eq(trigger_ext_d),
            trigger_ext_d.eq(external_trigger)
        ]
        self.comb += [
            self.trigger_re.eq(~trigger_ext_prev &  trigger_ext_d),
            self.trigger_fe.eq( trigger_ext_prev & ~trigger_ext_d)
        ]


class BaselineTriggerGenerator(TriggerGenerator):

    def __init__(self, data, trigger_level, treshold_length=4, name="baseline_trigger"):
        super().__init__(name)

        # Outputs
        self.trigger_re = Signal()  # CD: sys
        self.trigger_fe = Signal()  # CD: sys

        self.register_trigger(self.trigger_re, "re", ClockDomain("sys"))
        self.register_trigger(self.trigger_fe, "fe", ClockDomain("sys"))

        # # #

        assert len(data) == len(trigger_level), "Trigger level width must be equal to data width"
        
        self.trigger_level = trigger_level
        self.submodules.baseline_generator = baseline_gen = SignalBaseline(len(data))
        self.trigger_level_offset = trigger_level_offset = Signal.like(data)
        self.comb += [
            baseline_gen.i.eq(data),
            trigger_level_offset.eq(baseline_gen.o)
        ]

        data_prev = Signal(len(data) * treshold_length)

        above_comparison_list = [
            data_prev[i * len(data):(i + 1) * len(data)] >= trigger_level + trigger_level_offset for i in
                range(treshold_length)]
        below_comparison_list = [
            data_prev[i * len(data):(i + 1) * len(data)] <= trigger_level + trigger_level_offset for i in
                range(treshold_length)]
        data_above = Signal()
        data_below = Signal()

        self.comb += [
            data_above.eq(reduce(and_, above_comparison_list)),
            data_below.eq(reduce(and_, below_comparison_list))
        ]

        above_prev = Signal()
        below_prev = Signal()

        self.sync += [
            data_prev.eq((data_prev << len(data)) | data),

            If(data_above & ~above_prev, self.trigger_re.eq(1)).Else(self.trigger_re.eq(0)),
            If(data_below & ~below_prev, self.trigger_fe.eq(1)).Else(self.trigger_fe.eq(0)),

            above_prev.eq(data_above),
            below_prev.eq(data_below)
        ]


class RtioBaselineTriggerGenerator(BaselineTriggerGenerator):

    def __init__(self, data, treshold_length=4, name="baseline_trigger"):
        
        self.rtlink = rtlink.Interface(rtlink.OInterface(data_width=len(data)))

        # # #

        regs = [
             ("offset_level", len(data))
        ]
        csr = RtLinkCSR(regs, "baseline_trigger_generator")
        self.submodules.csr = csr

        trigger_level_sys = Signal.like(data)
        
        cdc = BusSynchronizer(len(data), "rio_phy", "sys")
        self.submodules += cdc

        self.comb += [
            cdc.i.eq(self.csr.offset_level),
            trigger_level_sys.eq(cdc.o)
        ]
            
        super().__init__(data, trigger_level_sys, treshold_length, name)