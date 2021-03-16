from artiq.coredevice import spi2 as spi
from artiq.coredevice.ttl import TTLInOut, TTLOut
from artiq.coredevice.edge_counter import EdgeCounter
from artiq.language.units import ns, us
from coredevice.ad9528 import AD9528
from coredevice.ad9528_default_config import AD9528_DEFAULT_CONFIG, AD9528_DEBUG_CONFIG
from coredevice.ads5296a import ADS5296A
from coredevice.tdc_gpx2 import TDCGPX2
from artiq.language.core import kernel


class FmcAdc100M10bTdc16cha:

    def __init__(self, dmgr, channel, with_trig, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        self.tdc_disable = [
            TTLOut(dmgr, self.channel + i, core_device) for i in range(4)
        ]

        self.idx_in = TTLOut(dmgr, self.channel + 4, core_device)
        self.adc_resetn = TTLOut(dmgr, self.channel + 5, core_device)
        self.adc_sync = TTLOut(dmgr, self.channel + 6, core_device)
        self.trig_term = TTLOut(dmgr, self.channel + 7, core_device)
        self.trig_dir = TTLOut(dmgr, self.channel + 8, core_device)
        self.ref_sel = TTLOut(dmgr, self.channel + 9, core_device)
        self.idx_src_sel = TTLOut(dmgr, self.channel + 10, core_device)

        self.adc_spi = spi.SPIMaster(dmgr, self.channel + 12, core_device=core_device)
        self.tdc_spi = spi.SPIMaster(dmgr, self.channel + 11, core_device=core_device)

        self.tdc_csn = [TTLOut(dmgr, self.channel + 81 + i, core_device) for i in range(4)]
        self.clock_csn = TTLOut(dmgr, self.channel + 81 + 4, core_device)
        self.adc_csn = [TTLOut(dmgr, self.channel + 81 + 5 + i, core_device) for i in range(2)]

        self.adc = [
            ADS5296A(dmgr, self.channel + 13 + i*9, self.adc_spi, self.adc_csn[i], core_device=core_device, spi_freq=500_000) for i in range(2)
        ]
        self.tdc = [
            TDCGPX2(dmgr, self.channel + 31 + i*12, self.tdc_spi, self.tdc_csn[i], core_device=core_device, spi_freq=1_000_000) for i in range(4)
        ]

        if with_trig:
            self.trig = TTLInOut(dmgr, channel + 88, core_device)
            freq_counter_channel_offset = channel + 89
        else:
            freq_counter_channel_offset = channel + 88
        
        self.clk0_ttl = TTLInOut(dmgr, freq_counter_channel_offset+0, core_device)
        self.clk0_edge_counter = EdgeCounter(dmgr, freq_counter_channel_offset+1, core_device=core_device)
        self.clk1_ttl = TTLInOut(dmgr, freq_counter_channel_offset+2, core_device)
        self.clk1_edge_counter = EdgeCounter(dmgr, freq_counter_channel_offset+3, core_device=core_device)

        self.adc0_lclk_ttl = TTLInOut(dmgr, freq_counter_channel_offset+4, core_device)
        self.adc0_lclk_edge_counter = EdgeCounter(dmgr, freq_counter_channel_offset+5, core_device=core_device)
        self.adc1_lclk_ttl = TTLInOut(dmgr, freq_counter_channel_offset+6, core_device)
        self.adc1_lclk_edge_counter = EdgeCounter(dmgr, freq_counter_channel_offset+7, core_device=core_device)

        self.clock = AD9528(dmgr=dmgr,
                            spi_device=self.tdc_spi,
                            chip_select=self.clock_csn,
                            spi_freq=500_000,
                            config=AD9528_DEFAULT_CONFIG,# AD9528_DEBUG_CONFIG, #AD9528_DEFAULT_CONFIG, #,
                            core_device=core_device)

    @kernel
    def deactivate_all_spi_devices(self):
        for ttl in self.tdc_csn:
            ttl.on()
        self.clock_csn.on()
        for ttl in self.adc_csn:
            ttl.on()

    @kernel
    def reset_ad9528_and_adc(self):
        self.core.break_realtime()
        self.adc_sync.off()
        self.adc_resetn.off()
        delay(100*us)
        self.adc_resetn.on()
        
    @kernel
    def initialize(self):
        self.deactivate_all_spi_devices()
        self.reset_ad9528_and_adc()
        self.clock.initialize()
        for adc in self.adc:
            adc.initialize()
        for tdc in self.tdc:
            tdc.initialize()
        # TDC counter reset from FMC
        # self.idx_src_sel.on()
        # for i in range(4):
        #     self.tdc_disable[i].off()

