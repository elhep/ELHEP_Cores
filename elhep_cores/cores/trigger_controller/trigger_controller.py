from migen import *
from migen.fhdl import *

from migen.fhdl.specials import Memory
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from migen.genlib.io import DifferentialInput
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink
from functools import reduce
from operator import or_, and_
import json
from elhep_cores.cores.trigger_controller.trigger_generators import RtioBaselineTriggerGenerator


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

        # print(trigger_generators)
        # print(trigger_generators[0].triggers)


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
        

        self.sw_trigger_signals = rtlink_trigger_generator_signals = [Signal() for _ in range(rtlink_triggers_no)]
        rtlink_trigger_array = Array(rtlink_trigger_generator_signals)

        trigger_generator_labels += [f"SW Trigger {i}" for i in range(rtlink_triggers_no)]

        self.trigger_channel_signals = trigger_channel_signals = [dsc["signal"] for dsc in trigger_channels]
        self.trigger_channel_labels = trigger_channel_labels = [dsc["label"] for dsc in trigger_channels]

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

        address_width = len(Signal(max=len(trigger_generator_signals)*adr_per_channel))
        
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

        # print(len(trigger_generator_signals))

        # trigger_matrix = Array(Signal(matrix_row_width) for _ in range(len(trigger_channel_signals)))
        self.trigger_matrix = trigger_matrix = Array(Signal(matrix_row_width) for _ in range(len(trigger_generator_signals)))

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
                If(rtlink_address < len(trigger_generator_signals)*adr_per_channel,
                    trigger_matrix_view[rtlink_address].eq(self.rtlink.o.data)
                ).
                Else(
                    rtlink_trigger_array[rtlink_address-len(trigger_generator_signals)*adr_per_channel].eq(1)
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

        trigger_channel_reg_1 = Array(Signal() for i in range(len(trigger_generator_signals)))
        trigger_channel_reg_2 = Array(Signal() for i in range(len(trigger_generator_signals)))
        self.trigger_channel_out   = Array(Signal() for i in range(len(trigger_generator_signals)))

        for trigger_channel, trigger_matrix_row, reg1, reg2, out in zip(trigger_channel_signals,
                                                                   trigger_matrix, trigger_channel_reg_1, trigger_channel_reg_2, self.trigger_channel_out):
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
                If((reg1 == reg2) & (reg2 == 1),
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

        self.trigger_generators = []
        self.trigger_channels = []


        prefix = f"fmc_1_adc_1"
        cd_renamer = ClockDomainsRenamer({"dclk": f"{prefix}_dclk"})

        data_i = Array(Signal(10) for _ in range(trig_gen_no))
        
        for channel in range(trig_gen_no):

            trigger = Signal()
            self.trigger_channels.append(
                {"signal": trigger, "label": f"{prefix}_daq{channel}"}
            )
            
            baseline_tg = cd_renamer(RtioBaselineTriggerGenerator(
                data=data_i[channel],
                name=f"{prefix}_daq{channel}_baseline_tg"
            ))
            setattr(self.submodules, f"{prefix}_daq{channel}_baseline_tg", baseline_tg)
            self.trigger_generators.append(baseline_tg)





        # trigger_generator_signals = [Signal(name=f"trigger_{i}") for i in range(trig_gen_no)]
        # trigger_generator_labels = [f"TG{i}" for i in range(trig_gen_no)]
        # print(trigger_generator_signals)

        # trigger_channel_signals = [Signal(name=f"trigger_channel_out{i}") for i in range(trig_ch_no)]
        # trigger_channel_labels = [f"TI{i}" for i in range(trig_ch_no)]
        # trigger_channel_cd = [ClockDomain("sys") for i in range(trig_ch_no)]

        # trigger_generators = [{"signal": s,  "label": l, "cd" : cd} for s, l, cd in zip(trigger_generator_signals, trigger_generator_labels, trigger_channel_cd)]
        # trigger_channels = [{"signal": s, "label": l} for s, l in zip(trigger_channel_signals, trigger_channel_labels)]

        # trigger_baseline_tg = {}
        # triggers[0] = trigger_generators
        # trigger_baseline_tg[0].triggers = trigger_generators

        # print(triggers)
        # print(trigger_baseline_tg)

        # run_simulation(_simulate(RtioTriggerController(trigger_generators=self.trigger_generators, trigger_channels=self.trigger_channels)))

        self.submodules.dut = dut = RtioTriggerController(trigger_generators=self.trigger_generators, trigger_channels=self.trigger_channels)

        self.io = {
            'dclk_rst' : cd_dclk.rst,
            'dclk_clk' : cd_dclk.clk,
            'clk' : cd_rio_phy.clk,
            'rst' : cd_rio_phy.rst,

            'data_iv' : [*(data_i)],

            'trigger_channel_out_v' : [*(dut.trigger_channel_out)],

            'stb_o' : dut.rtlink.i.stb,
            'dat_o' : dut.rtlink.i.data,
            'stb_i' : dut.rtlink.o.stb,
            'addr_i' : dut.rtlink.o.address,
            'dat_i' : dut.rtlink.o.data
        }

        self.io_test = {
            cd_dclk.rst,
            cd_dclk.clk,
            cd_rio_phy.clk,
            cd_rio_phy.rst,

            *(data_i),

            *(dut.trigger_channel_out),

            dut.rtlink.i.stb,
            dut.rtlink.i.data,
            dut.rtlink.o.stb,
            dut.rtlink.o.address,
            dut.rtlink.o.data
        }

# def dclk_tick(dut,n): 
#     print(n)
#     assert n > 0, "ERROR: clock value must be > 0"
#     for i in range(n):
#         # print(i)
#         yield dut.io['dclk_clk'].eq(1)
#         yield
#         yield dut.io['dclk_clk'].eq(0)
#         yield
        

def testbench(dut):

    print("Start simulation")
    yield dut.io['rst'].eq(1)
    yield dut.io['dclk_rst'].eq(1)

    for i in range(2):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield

    yield dut.io['rst'].eq(0)
    yield dut.io['dclk_rst'].eq(0)

    for i in range(50):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield

    value = (yield dut.io['rst'])
    assert value == 0, "ERROR: Check reset signal"
    value = (yield dut.io['dclk_rst'])
    assert value == 0, "ERROR: Check reset signal"

    for i in range(5):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield

    print("Write configuration")
    #Addr + 1 to write 
    #Addr + 0 to read
    yield dut.io['addr_i'].eq(+1)
    yield dut.io['dat_i'].eq(0x1)
    yield dut.io['stb_i'].eq(1)
    for i in range(1):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['stb_i'].eq(0)
    yield dut.io['addr_i'].eq(0)
    for i in range(50):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield

    yield dut.io['data_iv'][0].eq(100)
    yield dut.io['data_iv'][1].eq(0)
    for i in range(30):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['data_iv'][0].eq(0)
    yield dut.io['data_iv'][1].eq(0)
    for i in range(30):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['addr_i'].eq(+1)
    yield dut.io['dat_i'].eq(0)
    yield dut.io['stb_i'].eq(1)
    for i in range(1):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['addr_i'].eq(2+1)
    yield dut.io['dat_i'].eq(5)
    yield dut.io['stb_i'].eq(1)
    for i in range(1):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['stb_i'].eq(0)
    yield dut.io['addr_i'].eq(0)
    for i in range(30):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['data_iv'][0].eq(100)
    for i in range(10):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
    yield dut.io['data_iv'][1].eq(100)

    # print(rst in module.io)
    # n = 100

    for i in range(50):
        yield dut.io['dclk_clk'].eq(1)
        yield
        yield dut.io['dclk_clk'].eq(0)
        yield
        # n = n - 1
        # if (dut.io['stb_i'] == 1): 
        #     print(1)
        # else:
        #     print(0)




        

# class hello_world(Module):
# 	def __init__(self):
# 		# declare registers
# 		self.counter = Signal(16)
# 		self.led = Signal()
# 		# define I/O
# 		self.ios = {self.led}
# 		# describe sequential process
# 		self.sync += self.counter.eq(self.counter + 1)
# 		self.sync += If(self.counter == Replicate(1,len(self.counter)), self.led.eq(~self.led))

# def _test(dut):
# 	i = 0
# 	last = (yield dut.led)
# 	while(1):
# 		curr = (yield dut.led)
# 		if (curr != last):
# 			print("LED = %d @clk %d"%(curr,i))
# 			i = 0
# 		last = curr
# 		yield
# 		i+=1

if __name__ == "__main__":

    from migen.build.xilinx import common
    # from gateware.simulation.common import update_tb

    print("\nRunning Sim...\n")

    module = ClockDomainsRenamer({"rio_phy" : "sys"})(SimulationWrapper())

    # module = SimulationWrapper()




    run_simulation( module, testbench(module), vcd_name="file.vcd")
    module = SimulationWrapper()
    verilog.convert(fi=module,
                    name="top",
                    # special_overrides=so,
                    ios=module.io_test,
                    create_clock_domains=True).write("trigger_controller.v")

    
    # update_tb("trigger_controller.v")

