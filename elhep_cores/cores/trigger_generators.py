from migen import *
from migen.genlib.io import DifferentialInput
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from artiq.gateware.rtio import rtlink
from elhep_cores.cores.dsp.baseline import SignalBaseline
from functools import reduce
from operator import and_, add
from elhep_cores.cores.rtlink_csr import RtLinkCSR
from elhep_cores.cores.pulse_extender import PulseExtender


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
        # # self.submodules.baseline_generator = baseline_gen = SignalBaseline(len(data))
        # self.trigger_level_offset = trigger_level_offset = Signal.like(data)
        # self.comb += [
        #     baseline_gen.i.eq(data),
        #     trigger_level_offset.eq(baseline_gen.o)
        # ]

        data_prev = Signal(len(data) * treshold_length)

        above_comparison_list = [
            # data_prev[i * len(data):(i + 1) * len(data)] > trigger_level + trigger_level_offset for i in
            #     range(treshold_length)]
            data_prev[i * len(data):(i + 1) * len(data)] > trigger_level for i in range(treshold_length)]
        below_comparison_list = [
            # data_prev[i * len(data):(i + 1) * len(data)] < trigger_level + trigger_level_offset for i in
            #     range(treshold_length)]
            data_prev[i * len(data):(i + 1) * len(data)] < trigger_level for i in range(treshold_length)]
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


class RtioTriggerGenerator(TriggerGenerator):

    def __init__(self, name="sw_trigger"):
        super().__init__(name)

        # Outputs
        self.trigger = Signal()  # CD: rio_phy
        self.register_trigger(self.trigger, "trigger", ClockDomain("rio_phy"))

         # Interface - rtlink
        self.rtlink = rtlink_iface = rtlink.Interface(
            rtlink.OInterface(data_width=1)
        )

        self.sync.rio_phy += [
            self.trigger.eq(0),
            If(rtlink_iface.o.stb, self.trigger.eq(1))
        ]


class RtioCoincidenceTriggerGenerator(TriggerGenerator):

    def __init__(self, name, generators, reset_pulse_length=50, pulse_max_length=255):
        super().__init__(name)
        assert pulse_max_length <= 31, "Pulse max length must be <= 31"
        
        self.pulse_length = Signal(max=pulse_max_length)
        self.trigger = Signal()
        self.register_trigger(self.trigger, "trigger", "rio_phy")
        
        self.trigger_in_signals = []
        self.trigger_in_labels  = []

        for generator in generators:
            for trigger in generator.triggers:            
                self._register_trigger_in(**trigger)

        self._add_logic()
        self._add_rtlink()        

    def _register_trigger_in(self, signal, label, cd=None):
        if len(self.trigger_in_signals >= 32):
                raise RuntimeError("Coincidence Trigger currently supports up to 32 input channels.")
        if cd is None:
            trigger_in_rio_phy = signal
        elif cd.name == "rio_phy":
            trigger_in_rio_phy = signal
        else:
            trigger_in_rio_phy = Signal()
            cdc = PulseSynchronizer(cd.name, "rio_phy")
            self.submodules += cdc
            self.comb += [
                cdc.i.eq(signal),
                trigger_in_rio_phy.eq(cdc.o)
            ]        
        self.trigger_in_signals.append(trigger_in_rio_phy)
        self.trigger_in_labels.append(label)

    def _add_logic(self):
        self.pulses = []

        for signal in self.trigger_in_signals:
            pe = ClockDomainsRenamer("rio_phy")(PulseExtender(len(self.pulse_length)))
            self.submodules += pe
            self.comb += [
                pe.i.eq(signal),
                pe.length.eq(self.pulse_length)
            ]
            self.pulses.append(pe.o)
        
        self.mask = Signal(len(self.pulses))
        self.enabled = Signal()

        product_elements = [(self.pulses[i] | ~self.mask[i]) for i in range(len(self.pulses))]
        product_elements.append(self.enabled)
        product = reduce(and_, product_elements)

        trigger_int = Signal()
        trigger_int_d = Signal()
        self.sync.rio_phy += [
            self.trigger.eq(trigger_int & ~trigger_int_d),
            trigger_int_d.eq(trigger_int),
            trigger_int.eq(product)
        ]

    def _add_rtlink(self):
        # Address [0]: wen
        # Address [1:]: 0 - config, 1 - mask
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=32, address_width=2),
            rtlink.IInterface(data_width=32, timestamped=False))

        rtlink_address = Signal.like(self.rtlink.o.address)
        rtlink_wen = Signal()
        self.comb += [
            rtlink_address.eq(self.rtlink.o.address[1:]),
            rtlink_wen.eq(self.rtlink.o.address[0]),
        ]

        self.sync.rio_phy += [
            self.rtlink.i.stb.eq(0),
            If(self.rtlink.o.stb & rtlink_wen & rtlink_address == 0,
                self.pulse_length.eq(self.rtlink.o.data[1:]),
                self.enabled.eq(self.rtlink.o.data[0])
            ).
            Elif(self.rtlink.o.stb & rtlink_wen & rtlink_address == 1,
                self.mask.eq(self.rtlink.o.data)
            ).
            Elif(self.rtlink.o.stb & ~rtlink_wen & rtlink_address == 0,
                self.rtlink.i.data.eq(Cat(self.enabled, self.pulse_length)),
                self.rtlink.i.stb.eq(1)
            ).
            Elif(self.rtlink.o.stb & ~rtlink_wen & rtlink_address == 1,
                self.rtlink.i.data.eq(self.mask),
                self.rtlink.i.stb.eq(1)
            )
        ]
