from migen.build.generic_platform import *

from misoc.cores import gpio

from artiq.gateware.rtio.phy.ttl_simple import *
from artiq.gateware.rtio.phy import ttl_serdes_7series
from artiq.gateware.rtio.phy.spi2 import SPIMaster
from artiq.gateware.rtio.phy.edge_counter import SimpleEdgeCounter
from artiq.gateware import rtio

from elhep_cores.cores.ads5296a_phy.ads5296a import ADS5296A_XS7
from elhep_cores.cores.tdcgpx2_phy.tdcgpx2 import TdcGpx2Phy

from elhep_cores.cores.xilinx import *
from elhep_cores.helpers.fmc import _FMC, _fmc_pin


class FmcAdc100M10b16chaTdc(_FMC):

    @classmethod
    def io(cls, fmc, iostd_single, iostd_diff):
        return [
            cls.diff_signal("trig", fmc, "HB", 12, iostd_diff),
            cls.diff_signal("idx_in", fmc, "LA", 32, iostd_diff),

            cls.diff_signal("adc_out_adclk", fmc, "HB", 0, iostd_diff, idx=0),
            cls.diff_signal("adc_out_lclk", fmc, "HB", 6, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out0", fmc, "HB", 2, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out1", fmc, "HB", 9, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out2", fmc, "HB", 8, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out3", fmc, "HB", 3, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out4", fmc, "HB", 5, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out5", fmc, "HB", 7, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out6", fmc, "HB", 4, iostd_diff, idx=0),
            cls.diff_signal("adc_out_out7", fmc, "HB", 1, iostd_diff, idx=0),

            cls.diff_signal("adc_out_adclk", fmc, "HA", 17, iostd_diff, idx=1),
            cls.diff_signal("adc_out_lclk", fmc, "HA", 1, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out0", fmc, "HA", 10, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out1", fmc, "HA", 15, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out2", fmc, "HA", 18, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out3", fmc, "HA", 14, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out4", fmc, "HA", 16, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out5", fmc, "HA", 12, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out6", fmc, "HA", 11, iostd_diff, idx=1),
            cls.diff_signal("adc_out_out7", fmc, "HA", 13, iostd_diff, idx=1),

            cls.diff_signal("tdc_out_lclkout", fmc, "HB", 17, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_frame0", fmc, "HB", 20, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_sdo0", fmc, "HB", 13, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_frame1", fmc, "HB", 15, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_sdo1", fmc, "HB", 19, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_frame2", fmc, "HB", 21, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_sdo2", fmc, "HB", 16, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_frame3", fmc, "HB", 14, iostd_diff, idx=0),
            cls.diff_signal("tdc_out_sdo3", fmc, "HB", 18, iostd_diff, idx=0),

            cls.diff_signal("tdc_out_lclkout", fmc, "LA", 17, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_frame0", fmc, "LA", 24, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_sdo0", fmc, "LA", 25, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_frame1", fmc, "LA", 26, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_sdo1", fmc, "LA", 21, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_frame2", fmc, "LA", 22, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_sdo2", fmc, "LA", 23, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_frame3", fmc, "LA", 19, iostd_diff, idx=1),
            cls.diff_signal("tdc_out_sdo3", fmc, "LA", 20, iostd_diff, idx=1),

            cls.diff_signal("tdc_out_lclkout", fmc, "LA", 0, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_frame0", fmc, "LA", 9, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_sdo0", fmc, "LA", 7, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_frame1", fmc, "LA", 8, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_sdo1", fmc, "LA", 5, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_frame2", fmc, "LA", 6, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_sdo2", fmc, "LA", 4, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_frame3", fmc, "LA", 3, iostd_diff, idx=2),
            cls.diff_signal("tdc_out_sdo3", fmc, "LA", 2, iostd_diff, idx=2),

            cls.diff_signal("tdc_out_lclkout", fmc, "HA", 0, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_frame0", fmc, "HA", 2, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_sdo0", fmc, "HA", 3, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_frame1", fmc, "HA", 7, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_sdo1", fmc, "HA", 8, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_frame2", fmc, "HA", 6, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_sdo2", fmc, "HA", 4, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_frame3", fmc, "HA", 5, iostd_diff, idx=3),
            cls.diff_signal("tdc_out_sdo3", fmc, "HA", 9, iostd_diff, idx=3),

            cls.diff_signal("tdc_dis", fmc, "HB", 10, iostd_diff, idx=0),
            cls.diff_signal("tdc_dis", fmc, "HA", 23, iostd_diff, idx=1),
            cls.diff_signal("tdc_dis", fmc, "LA", 1, iostd_diff, idx=2),
            cls.diff_signal("tdc_dis", fmc, "LA", 10, iostd_diff, idx=3),

            (cls.signal_name("adc_spi", fmc), 0,
             Subsignal("sck", Pins(_fmc_pin(fmc, "HA", 22, "p")), *(iostd_single["fmc{}_HA".format(fmc)])),
             Subsignal("miso", Pins(_fmc_pin(fmc, "HA", 21, "n")), *(iostd_single["fmc{}_HA".format(fmc)])),
             Subsignal("mosi", Pins(_fmc_pin(fmc, "LA", 16, "p")), *(iostd_single["fmc{}_LA".format(fmc)])),
             ),
            cls.single_signal("adc_spi_csn", fmc, "HA", 22, "n", iostd_single, idx=0),
            cls.single_signal("adc_spi_csn", fmc, "LA", 11, "n", iostd_single, idx=1),

            cls.single_signal("adc_resetn", fmc, "LA", 15, "p", iostd_single, idx=0),
            cls.single_signal("adc_sync", fmc, "LA", 30, "p", iostd_single, idx=0),

            (cls.signal_name("tdc_spi", fmc), 0,
             Subsignal("sck", Pins(_fmc_pin(fmc, "LA", 15, "n")), *(iostd_single["fmc{}_LA".format(fmc)])),
             Subsignal("miso", Pins(_fmc_pin(fmc, "LA", 16, "n")), *(iostd_single["fmc{}_LA".format(fmc)])),
             Subsignal("mosi", Pins(_fmc_pin(fmc, "LA", 13, "p")), *(iostd_single["fmc{}_LA".format(fmc)]))
             ),
            cls.single_signal("tdc_spi_csn", fmc, "LA", 31, "n", iostd_single, idx=0),
            cls.single_signal("tdc_spi_csn", fmc, "LA", 31, "p", iostd_single, idx=1),
            cls.single_signal("tdc_spi_csn", fmc, "LA", 12, "p", iostd_single, idx=2),
            cls.single_signal("tdc_spi_csn", fmc, "HA", 20, "n", iostd_single, idx=3),
            cls.single_signal("tdc_spi_csn", fmc, "LA", 14, "n", iostd_single, idx=4),  # CLK CSN

            # TDC INT and TDC PAR are not supported

            cls.single_signal("trig_term", fmc, "LA", 14, "p", iostd_single, idx=0),
            cls.single_signal("trig_dir", fmc, "LA", 13, "n", iostd_single, idx=0),
            cls.single_signal("ref_sel", fmc, "LA", 29, "p", iostd_single, idx=0),
            cls.single_signal("idx_src_sel", fmc, "LA", 30, "n", iostd_single, idx=0),

            # PGOOD is not supported
            # cls.single_signal("pgood", fmc, "LA", 29, "n", iostd_single, idx=0),

            (cls.signal_name("dac_i2c", fmc), 0,
             Subsignal("scl", Pins(_fmc_pin(fmc, "LA", 27, "n")), *(iostd_single["fmc{}_LA".format(fmc)])),
             Subsignal("sda", Pins(_fmc_pin(fmc, "LA", 27, "p")), *(iostd_single["fmc{}_LA".format(fmc)])),
             ),

            cls.single_signal("tp35", fmc, "LA", 18, "p", iostd_single, idx=0),
            cls.single_signal("tp36", fmc, "LA", 18, "n", iostd_single, idx=0),
            cls.single_signal("tp37", fmc, "HA", 20, "p", iostd_single, idx=0),
            cls.single_signal("tp38", fmc, "HA", 21, "p", iostd_single, idx=0),
            cls.single_signal("tp39", fmc, "HB", 11, "p", iostd_single, idx=0),
            cls.single_signal("tp40", fmc, "HB", 11, "n", iostd_single, idx=0),
        ]

    @classmethod
    def add_std(cls, target, fmc, iostd_single, iostd_diff, with_trig=False, adc_daq_samples=1024, tdc_daq_samples=1024):
        cls.add_extension(target, fmc, iostd_single, iostd_diff)

        # CFD DAC I2C

        dac_i2c = target.platform.request(cls.signal_name("dac_i2c", fmc))
        bus_id = target.add_i2c_bus(dac_i2c.scl, dac_i2c.sda, f"FMC{fmc} DAC I2C")
        target.submodules.i2c = gpio.GPIOTristate([dac_i2c.scl, dac_i2c.sda])
        target.csr_devices.append("i2c")
        
        for i, address in enumerate([0x48, 0x49]):
            target.register_coredevice(
                device_id=f"fmc{fmc}_cfd_offset_dac{i}",
                module="elhep_cores.coredevice.dac7578", class_name="DAC7578",
                arguments={"busno": 0, "address": address << 1})  # FIXME: use valid bus id
        
        # IOs

        for i in range(4):
            pads = target.platform.request(cls.signal_name("tdc_dis", fmc), i)
            phy = Output(pads.p, pads.n)
            target.submodules += phy
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy), 
                device_id=f"fmc{fmc}_tdc_dis{i}",
                module="artiq.coredevice.ttl",
                class_name="TTLOut")

        for sn in ["idx_in", "adc_resetn", "adc_sync", "trig_term", "trig_dir", "ref_sel", "idx_src_sel"]:
            pads = target.platform.request(cls.signal_name(sn, fmc), 0)
            if hasattr(pads, "p"):
                phy = Output(pads.p, pads.n)
            else:
                phy = Output(pads)
            target.submodules += phy
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy), 
                device_id=f"fmc{fmc}_{sn}",
                module="artiq.coredevice.ttl",
                class_name="TTLOut")

        # SPI Configuration interfaces

        tdc_spi = target.platform.request(cls.signal_name("tdc_spi", fmc), 0)
        tdc_spi_pads = Signal()
        tdc_spi_pads.clk = tdc_spi.sck
        tdc_spi_pads.miso = tdc_spi.miso
        tdc_spi_pads.mosi = tdc_spi.mosi
        tdc_spi_pads.cs_n = Signal(5)
        
        phy = SPIMaster(tdc_spi_pads)
        target.submodules += phy
        target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy), 
                device_id=f"fmc{fmc}_tdc_spi",
                module="artiq.coredevice.spi2",
                class_name="SPIMaster")

        adc_spi = target.platform.request(cls.signal_name("adc_spi", fmc), 0)
        adc_spi_pads = Signal()
        adc_spi_pads.clk = adc_spi.sck
        adc_spi_pads.miso = adc_spi.miso
        adc_spi_pads.mosi = adc_spi.mosi
        adc_spi_pads.cs_n = Signal(2)        

        phy = SPIMaster(adc_spi_pads)
        target.submodules += phy
        target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy), 
                device_id=f"fmc{fmc}_adc_spi",
                module="artiq.coredevice.spi2",
                class_name="SPIMaster")

        csn_pads = [
            *[target.platform.request(cls.signal_name("tdc_spi_csn", fmc), i) for i in range(5)],
            *[target.platform.request(cls.signal_name("adc_spi_csn", fmc), i) for i in range(2)]
        ]

        for i, pad in enumerate(csn_pads):
            phy = Output(pad)
            target.submodules += phy
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy), 
                device_id=f"fmc{fmc}_csn{i}",
                module="artiq.coredevice.ttl",
                class_name="TTLOut")

        # Clocking

        target.register_coredevice(
            device_id=f"fmc{fmc}_clock_dist",
            module="elhep_cores.coredevice.ad9528",
            class_name="AD9528",
            arguments={
                "spi_device": f"fmc{fmc}_tdc_spi",
                "chip_select": f"fmc{fmc}_csn4"
            }
        )

        # ADC

        for adc_id in range(2):
            dclk_name = "fmc{}_adc{}_dclk".format(fmc, adc_id)
            adc_lclk = target.platform.request(cls.signal_name("adc_out_lclk", fmc), adc_id)
            phy = ADS5296A_XS7(
                adclk_i=target.platform.request(cls.signal_name("adc_out_adclk", fmc), adc_id),
                lclk_i=adc_lclk,
                dat_i=[target.platform.request(cls.signal_name("adc_out_out{}".format(i), fmc), adc_id) for i in range(8)])
            target.platform.add_period_constraint(adc_lclk.p, 2.)
            target.platform.add_period_constraint(phy.cd_adclk_clkdiv.clk, 10.)
            target.platform.add_period_constraint(phy.lclk_bufio, 2.)
            target.platform.add_period_constraint(phy.lclk, 10.)
            phy_renamed_cd = ClockDomainsRenamer({"adclk_clkdiv": dclk_name})(phy)
            setattr(target.submodules, "fmc{}_adc{}_phy".format(fmc, adc_id), phy_renamed_cd)
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy.csr), 
                device_id=f"fmc{fmc}_adc{adc_id}_phycsr",
                module="elhep_cores.coredevice.rtlink_csr",
                class_name="RtlinkCsr",
                arguments={
                    "regs": phy.csr.regs
                })

            target.register_coredevice(
                device_id=f"fmc{fmc}_adc{adc_id}_control",
                module="elhep_cores.coredevice.ads5296a",
                class_name="ADS5296A",
                arguments={
                    "spi_device": f"fmc{fmc}_adc_spi",
                    "phy_csr": f"fmc{fmc}_adc{adc_id}_phycsr",
                    "chip_select": f"fmc{fmc}_csn{adc_id+5}",
                    "spi_freq": 500_000
                }
            )

        # TDC

        for tdc_id in range(4):
            dclk_name = "fmc{}_tdc{}_dclk".format(fmc, tdc_id)
            fs = [target.platform.request(cls.signal_name("tdc_out_frame{}".format(i), fmc), tdc_id) for i in range(4)]
            ds = [target.platform.request(cls.signal_name("tdc_out_sdo{}".format(i), fmc), tdc_id) for i in range(4)]
            phy = TdcGpx2Phy(data_clk_i=target.platform.request(cls.signal_name("tdc_out_lclkout", fmc), tdc_id),
                             frame_signals_i=fs,
                             data_signals_i=ds)
            target.platform.add_period_constraint(phy.cd_dclk.clk, 4.)
            phy_renamed_cd = ClockDomainsRenamer({"dclk": dclk_name})(phy)
            setattr(target.submodules, "fmc{}_tdc{}_phy".format(fmc, tdc_id), phy_renamed_cd)
            for idx, channel in enumerate(phy.phy_channels):
                target.add_rtio_channels(
                    channel=rtio.Channel.from_phy(channel.csr),
                    device_id=f"fmc{fmc}_tdc{tdc_id}_phycsr_{idx}",
                    module="elhep_cores.coredevice.rtlink_csr",
                    class_name="RtlinkCsr",
                    arguments={
                        "regs": channel.csr.regs
                    })

            target.register_coredevice(
                device_id=f"fmc{fmc}_tdc{tdc_id}_control",
                module="elhep_cores.coredevice.tdc_gpx2",
                class_name="TDCGPX2",
                arguments={
                    "spi_device": f"fmc{fmc}_tdc_spi",
                    "phy_csr_prefix": f"fmc{fmc}_tdc{tdc_id}_phycsr_",
                    "chip_select": f"fmc{fmc}_csn{tdc_id+0}",
                    "spi_freq": 1_000_000
                }
            )


        if with_trig:
            pads = target.platform.request(cls.signal_name("trig", fmc))
            phy = ttl_serdes_7series.InOut_8X(pads.p, pads.n)
            target.submodules += phy
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy, ififo_depth=64), 
                device_id=f"fmc{fmc}_trig",
                module="artiq.coredevice.ttl",
                class_name="TTLInOut")
    
        # Frequency counters

        clk0_m2c_pads = target.platform.request(f"fmc{fmc}_clk0_m2c")
        phy_clk0_m2c = Input(clk0_m2c_pads.p, clk0_m2c_pads.n)
        clk0_m2c_edge_counter = SimpleEdgeCounter(phy_clk0_m2c.input_state)
        target.submodules += [phy_clk0_m2c, clk0_m2c_edge_counter]

        target.add_rtio_channels(
            channel=rtio.Channel.from_phy(phy_clk0_m2c), 
            device_id=f"fmc{fmc}_clk0_m2c_ttl_input",
            module="artiq.coredevice.ttl",
            class_name="TTLInOut")
        target.add_rtio_channels(
            channel=rtio.Channel.from_phy(clk0_m2c_edge_counter), 
            device_id=f"fmc{fmc}_clk0_m2c_edge_counter",
            module="artiq.coredevice.edge_counter",
            class_name="EdgeCounter")

        clk1_m2c_pads = target.platform.request(f"fmc{fmc}_clk1_m2c")
        phy_clk1_m2c = Input(clk1_m2c_pads.p, clk1_m2c_pads.n)
        clk1_m2c_edge_counter = SimpleEdgeCounter(phy_clk1_m2c.input_state)
        target.submodules += [phy_clk1_m2c, clk1_m2c_edge_counter]

        target.add_rtio_channels(
            channel=rtio.Channel.from_phy(phy_clk1_m2c), 
            device_id=f"fmc{fmc}_clk1_m2c_ttl_input",
            module="artiq.coredevice.ttl",
            class_name="TTLInOut")
        target.add_rtio_channels(
            channel=rtio.Channel.from_phy(clk1_m2c_edge_counter), 
            device_id=f"fmc{fmc}_clk1_m2c_edge_counter",
            module="artiq.coredevice.edge_counter",
            class_name="EdgeCounter")

        # Debug counters

        for adc_id in range(2):
            adc_phy = getattr(target, f"fmc{fmc}_adc{adc_id}_phy")
            phy_adc_lclk = Input(adc_phy.lclk)
            phy_adc_lclk_counter = SimpleEdgeCounter(phy_adc_lclk.input_state)
            target.submodules += [phy_adc_lclk, phy_adc_lclk_counter]

            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy_adc_lclk), 
                device_id=f"fmc{fmc}_phy_adc{adc_id}_lclk_input",
                module="artiq.coredevice.ttl",
                class_name="TTLInOut")
            target.add_rtio_channels(
                channel=rtio.Channel.from_phy(phy_adc_lclk_counter), 
                device_id=f"fmc{fmc}_phy_adc{adc_id}_lclk_counter",
                module="artiq.coredevice.edge_counter",
                class_name="EdgeCounter")

        # Register itself

        target.register_coredevice(
                device_id=f"fmc{fmc}",
                module="elhep_cores.coredevice.fmc_adc100M_10b_tdc_16cha",
                class_name="FmcAdc100M10bTdc16cha",
                arguments={
                    "prefix": "fmc1"
                })

            
             
