from functools import reduce
from operator import or_, and_
import json

from migen import *
from migen.fhdl import *
from migen.fhdl.specials import Memory
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from migen.genlib.io import DifferentialInput
from migen.fhdl import verilog

from artiq.gateware.rtio import rtlink

from elhep_cores.cores.trigger_controller.trigger_generators import TriggerGenerator
from elhep_cores.simulation.common import update_tb


def signal_to_array(signal, row_width=32):
    rows_num = (len(signal)+(row_width-1))//row_width
    rows = [signal[i*row_width:(i+1)*row_width] for i in range(rows_num)]
    return Array(rows)       
    

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


class RtioTriggerController(Module):

    def register_trigger_in(self, signal, label, cd):
        # CDC
        if cd.name == "rio_phy":
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

    def register_trigger_out(self, signal, label):
        self.trigger_out_signals.append(signal)
        self.trigger_out_labels.append(label)

    def add_rtio_support(self, layout_path=None):
        assert len(self.lengths[0]) <= 32, "Pulse max width greater that 2**32-1 not supported! Dude, o'rly?"

        # RTLink interface logic
        enable_array = signal_to_array(self.en_mask)
        mask_arrays = [signal_to_array(mask) for mask in self.masks]
        
        register_array = [*enable_array]
        for mask in mask_arrays:
            register_array += mask
        register_array += self.lengths
        register_array = Array(register_array)

        adr_per_mask = len(mask_arrays[0])
        address_width = len(Signal(max=len(register_array)))+1
        
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=32, address_width=address_width),
            rtlink.IInterface(data_width=32, timestamped=False))

        rtlink_address = Signal.like(self.rtlink.o.address)
        rtlink_wen = Signal()
        self.comb += [
            rtlink_address.eq(self.rtlink.o.address[1:]),
            rtlink_wen.eq(self.rtlink.o.address[0]),
        ]

        self.sync.rio_phy += [
            self.rtlink.i.stb.eq(0),
            If(self.rtlink.o.stb & rtlink_wen,
                register_array[rtlink_address].eq(self.rtlink.o.data)
            ).
            Elif(self.rtlink.o.stb & ~rtlink_wen,
                self.rtlink.i.data.eq(register_array[rtlink_address]),
                self.rtlink.i.stb.eq(1)
            )
        ]

        # RTLink interface layout
        if layout_path is None:
            return

        mask_base_offset = len(enable_array)
        mask_layout = {}

        for idx, label in enumerate(self.trigger_in_labels):
            mask_layout[label] = {
                "address_offset": idx // 32,
                "bit_offset": idx % 32,
                "pulse_length_offset": mask_base_offset + adr_per_mask*len(self.trigger_out_labels)+idx 
            }
        
        output_channels = {}

        for idx, label in enumerate(self.trigger_out_labels):
            output_channels[label] = {
                "en_offset": idx // 32,
                "en_bit_offset": idx % 32,
                "mask_address": mask_base_offset + adr_per_mask*idx 
            }

        layout = {"output_channels": output_channels, "mask_layout": mask_layout}

        with open(layout_path, "w") as f:
            json.dump(layout, fp=f, indent=4)

    def __init__(self, trigger_generators, trigger_channels, pulse_max_length=255, layout_path=None):
    
        # Get signals and labels in the rio_phy domain
        self.trigger_in_signals = []
        self.trigger_in_labels  = []
        for tg in trigger_generators:
            for trigger in tg.triggers:
                self.register_trigger_in(**trigger)
        
        # Extended pulses
        self.pulses = []
        self.lengths = [Signal(max=pulse_max_length, reset=32) for _ in self.trigger_in_signals]
        for signal, length in zip(self.trigger_in_signals, self.lengths):
            pe = ClockDomainsRenamer("rio_phy")(PulseExtender(pulse_max_length))
            self.submodules += pe
            self.comb += [
                pe.i.eq(signal),
                pe.length.eq(length)
            ]
            self.pulses.append(pe.o)
        
        # Get output channels
        self.trigger_out_signals = []
        self.trigger_out_labels = []
        for channel in trigger_channels:
            self.register_trigger_out(**channel)

        # Every channel has its own trigger mask
        self.masks = [Signal(len(self.pulses)) for _ in self.trigger_out_signals]

        # Channel enabled mask
        self.en_mask = Signal(len(self.trigger_out_signals))
        
        # Expression for trigger: (pulse[0] + ~mask[0]) & (pulse[1] + ~mask[1]) & ...
        for idx, (trigger_out, mask) in enumerate(zip(self.trigger_out_signals, self.masks)):
            product_elements = [(self.pulses[i] | ~mask[i]) for i in range(len(self.pulses))]
            product_elements.append(self.en_mask[idx])
            product = reduce(and_, product_elements)
            trigger_int = Signal()
            trigger_int_prev = Signal()
            self.sync.rio_phy += [
                trigger_out.eq(trigger_int & ~trigger_int_prev),
                trigger_int_prev.eq(trigger_int),
                trigger_int.eq(product)
            ]
        
        self.add_rtio_support(layout_path=layout_path)


class SimulationWrapper(Module):

    def __init__(self, generators=34, monitors=34):
        trigger_generator = TriggerGenerator("fake_gen")
        self.submodules += trigger_generator

        trigger_drivers = [Signal(name=f"trigger_driver_{i}") for i in range(generators)]
        clock_domains = [ClockDomain(f"trigger_cd_{i}", reset_less=True) for i, _ in enumerate(trigger_drivers)]
        for i, (td, cd) in enumerate(zip(trigger_drivers, clock_domains)):
            self.clock_domains += cd
            trigger_generator.register_trigger(td, f"trigger_driver_{i}", cd)

        trigger_channels = [
            {"label": f"trigger_ch_{i}", "signal": Signal(name=f"trigger_monitor_{i}")} for i in range(monitors)
        ]

        self.submodules.dut = dut = RtioTriggerController([trigger_generator], trigger_channels, layout_path="trigger_controller.json")

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain(reset_less=True)
        self.io = {
            dut.rtlink.i.stb,
            dut.rtlink.i.data,
            dut.rtlink.o.stb,
            dut.rtlink.o.address,
            dut.rtlink.o.data,
            self.cd_rio_phy.clk,
            *[td for td in trigger_drivers],
            *[cd.clk for cd in clock_domains],
            *[tc["signal"] for tc in trigger_channels],
        }


if __name__ == "__main__":
    module = SimulationWrapper(generators=34, monitors=35)
    verilog.convert(fi=module,
                    name="top",
                    ios=module.io,
                    create_clock_domains=False).write("dut.v")
    update_tb("dut.v")

