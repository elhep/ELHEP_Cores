from migen import *
from migen.fhdl.specials import Memory
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from migen.genlib.io import DifferentialInput
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink
from functools import reduce
from operator import or_, and_
import json
from elhep_cores.cores.trigger_controller.trigger_generators import TriggerGenerator


def divide_chunks(l, n): 
    for i in range(0, len(l), n):  
        yield l[i:i + n] 


class RtioTriggerController(Module):

    def __init__(self, trigger_generators, trigger_channels, rtlink_triggers_no=4, signal_delay=23):
        
        # RTLink

        # Address map:
        #  0: channel 0 trigger configuration
        #  1: channel 1 trigger configuration
        #  ...
        #  channel_no-1: channel channel_no-1 trigger configuration
        #  channel_no: manual trigger 0
        #  channel_no+1: manual trigger 1
        #  ...
        #  channel_no+rtlink_triggers_no: manual trigger rtlink_triggers_no-1
        # Address LSB is wen

        trigger_generator_signals = []
        trigger_generator_labels = []

        for tg in trigger_generators:
            for trigger in tg.triggers:
                cdc = PulseSynchronizer(trigger['cd'].name, "rio_phy")
                self.submodules += cdc
                trigger_rio_phy = Signal()
                self.comb += [
                    cdc.i.eq(trigger['signal']),
                    trigger_rio_phy.eq(cdc.o)
                ]
                trigger_generator_signals.append(trigger_rio_phy)
                trigger_generator_labels.append(trigger['label'])
        

        rtlink_trigger_generator_signals = [Signal() for _ in range(rtlink_triggers_no)]
        rtlink_trigger_array = Array(rtlink_trigger_generator_signals)

        trigger_generator_labels += [f"SW Trigger {i}" for i in range(rtlink_triggers_no)]

        trigger_channel_signals = [dsc["signal"] for dsc in trigger_channels]
        trigger_channel_labels = [dsc["label"] for dsc in trigger_channels]

        trigger_generators_num = len(trigger_generator_signals) + len(rtlink_trigger_generator_signals)
        adr_per_channel = (trigger_generators_num+31)//32

        trigger_rtlink_layout = {}
        trigger_channels = {}

        
        matrix_row_width = len(trigger_generator_signals)


        with open("trigger_rtlink_layout.txt", "w+") as fp:
            for row, elements in enumerate(list(divide_chunks(trigger_generator_labels, 32))):
                print(f"Trigger matrix row {row} layout (bit number, LSB to MSB):", file=fp)
                for i, tg in enumerate(elements):
                    print(f" * {i} {tg}", file=fp)
                    tg_id = tg.lower().replace(" ", "_")
                    trigger_rtlink_layout[tg_id] = {"address_offset": row, "word_offset": i}

            print("", file=fp)
            print("Trigger channels:", file=fp)
            for idx, tc in enumerate(trigger_channel_labels):
                start = idx * adr_per_channel
                stop = (idx+1) * adr_per_channel - 1
                trigger_ch_id = tc.lower().replace(" ", "_")
                trigger_channels[trigger_ch_id] = start
                print(f" * {start}-{stop}: {tc}", file=fp)
     
        with open("trigger_rtlink_layout.json", "w+") as fp:
            json.dump(
                {
                    "channel_layout": trigger_rtlink_layout, 
                    "channels": trigger_channels, 
                    "sw_trigger_start": len(trigger_generators), 
                    "sw_trigger_num": rtlink_triggers_no
                }, fp=fp)

        address_width = len(Signal(max=len(trigger_channel_signals)*adr_per_channel))
        
        if adr_per_channel > 1:
            iface_width = 32
        else:
            iface_width = matrix_row_width

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=iface_width, address_width=address_width),
            rtlink.IInterface(data_width=iface_width, timestamped=False))

        # trigger_matrix_n_x_n = []
        # for i in range(len(trigger_generator_signals)):
        #     trigger_matrix = Array(Signal(matrix_row_width) for _ in range(len(trigger_channel_signals)))
        #     trigger_matrix_n_x_n.append(trigger_matrix)


        trigger_matrix = Array(Signal(matrix_row_width) for _ in range(len(trigger_channel_signals)))

        trigger_matrix_signals = []
        for ch in range(len(trigger_channels)):
            for i in range(adr_per_channel):
                if i != adr_per_channel-1:
                    trigger_matrix_signals.append(trigger_matrix[ch][i*32:(i+1)*32])
                else:
                    trigger_matrix_signals.append(trigger_matrix[ch][i*32:])

        trigger_matrix_view = Array(trigger_matrix_signals)

        # RTLink support

        rtlink_address = Signal.like(self.rtlink.o.address)
        rtlink_wen = Signal()
        self.comb += [
            rtlink_address.eq(self.rtlink.o.address[1:]),
            rtlink_wen.eq(self.rtlink.o.address[0]),
        ]

        self.sync.rio_phy += [
            self.rtlink.i.stb.eq(0),
            *([rtlink_trigger.eq(0) for rtlink_trigger in rtlink_trigger_generator_signals]),

            If(self.rtlink.o.stb & rtlink_wen,
                If(rtlink_address < len(trigger_channel_signals)*len(trigger_channel_signals)*adr_per_channel,
                    trigger_matrix_view[rtlink_address].eq(self.rtlink.o.data)
                ).
                Else(
                    rtlink_trigger_array[rtlink_address-len(trigger_channel_signals)*adr_per_channel].eq(1)
                )).
            Elif(self.rtlink.o.stb & ~rtlink_wen,
                self.rtlink.i.data.eq(trigger_matrix_view[rtlink_address]),
                self.rtlink.i.stb.eq(1)
            )
        ]

        # Trigger computation

        trigger_delay_generator_signals_cnt = Array(Signal(max=32) for _ in range(len(trigger_generator_signals)))
        trigger_delay_generator_signals = Array(Signal() for _ in range(len(trigger_generator_signals)))

        for i in range(len(trigger_generator_signals)):
            self.sync.rio_phy += [
                If(trigger_generator_signals[i] == 1,
                    trigger_delay_generator_signals_cnt[i].eq(signal_delay),
                    trigger_delay_generator_signals[i].eq(1)
                ).Else(
                    If(trigger_delay_generator_signals_cnt[i] > 0,
                       trigger_delay_generator_signals_cnt[i].eq(trigger_delay_generator_signals_cnt[i] - 1)
                    ).Else(
                        trigger_delay_generator_signals[i].eq(0)
                    )
                )
            ]

        trigger_channel_reg_1 = Array(Signal() for _ in range(len(trigger_generator_signals)))
        trigger_channel_reg_2 = Array(Signal() for _ in range(len(trigger_generator_signals)))
        trigger_channel_out   = Array(Signal() for _ in range(len(trigger_generator_signals)))

        for trigger_channel, trigger_matrix_row, reg1, reg2, out in zip(trigger_channel_signals,
                                                                   trigger_matrix, trigger_channel_reg_1, trigger_channel_reg_2, trigger_channel_out):
            self.comb += [
                trigger_channel.eq(
                    # reduce(or_, Cat(rtlink_trigger_generator_signals)) |
                    # reduce(and_,
                    #        ((Cat(trigger_delay_generator_signals) & trigger_matrix[trigger_matrix_row]) | ~trigger_matrix_row)
                    #        )
                    reduce(or_, Cat(rtlink_trigger_generator_signals)) |
                    reduce(and_,
                           ((Cat(trigger_delay_generator_signals) & (Cat(trigger_matrix_row))) | ~Cat(trigger_matrix_row))
                           )
                ),
                If(reg1 == reg2,
                   out.eq(1)
                   ).Else(
                    out.eq(0)
                )
            ]
            self.sync.rio_phy += [
                reg1.eq(trigger_channel),
                reg2.eq(~reg1),

            ]




class SimulationWrapper(Module):

    def __init__(self):

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_dclk = cd_dclk = ClockDomain()

        trig_gen_no = 2
        trig_ch_no = 2

        trigger_generator_signals = [Signal(name=f"trigger_{i}") for i in range(trig_gen_no)]
        trigger_generator_labels = [f"TG{i}" for i in range(trig_gen_no)]
        print(trigger_generator_signals)

        trigger_channel_signals = [Signal(name=f"trigger_channel_out{i}") for i in range(trig_ch_no)]
        trigger_channel_labels = [f"TI{i}" for i in range(trig_ch_no)]

        trigger_generators = [{"signal": s, "label": l} for s, l in zip(trigger_generator_signals, trigger_generator_labels)]
        trigger_channels = [{"signal": s, "label": l} for s, l in zip(trigger_channel_signals, trigger_channel_labels)]

        self.submodules.dut = dut = RtioTriggerController(trigger_generators=trigger_generators, trigger_channels=trigger_channels)

        self.io = {
            cd_dclk.rst,
            cd_dclk.clk,
            cd_rio_phy.clk,
            cd_rio_phy.rst,

            *(trigger_generator_signals),
            *(trigger_channel_signals),

            dut.rtlink.i.stb,
            dut.rtlink.i.data,
            dut.rtlink.o.stb,
            dut.rtlink.o.address,
            dut.rtlink.o.data
        }

if __name__ == "__main__":

    from migen.build.xilinx import common
    # from gateware.simulation.common import update_tb

    module = SimulationWrapper()

    verilog.convert(fi=module,
                    name="top",
                    # special_overrides=so,
                    ios=module.io,
                    create_clock_domains=False).write("trigger_controller.v")
    # update_tb("trigger_controller.v")