from artiq.language.units import ns, us, ms
from artiq.language.core import kernel


class FmcAdc100M10bTdc16cha:

    def __init__(self, dmgr, prefix, core_device="core"):
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        self.tdc_disable = [dmgr.get(f"{prefix}_tdc_dis{i}") for i in range(4)]
        self.idx_in = dmgr.get(f"{prefix}_idx_in")
        self.adc_resetn = dmgr.get(f"{prefix}_adc_resetn")
        self.adc_sync = dmgr.get(f"{prefix}_adc_sync")
        self.trig_term = dmgr.get(f"{prefix}_trig_term")
        self.trig_dir = dmgr.get(f"{prefix}_trig_dir")
        self.ref_sel = dmgr.get(f"{prefix}_ref_sel")
        self.idx_src_sel = dmgr.get(f"{prefix}_idx_src_sel")
        self.clock = dmgr.get(f"{prefix}_clock_dist")
        self.adc = [dmgr.get(f"{prefix}_adc{i}_control") for i in range(2)]
        self.tdc = [dmgr.get(f"{prefix}_tdc{i}_control") for i in range(4)]

        self.adc_spi = dmgr.get(f"{prefix}_adc_spi")
        self.tdc_spi = dmgr.get(f"{prefix}_tdc_spi")

        self.tdc_csn = [dmgr.get(f"{prefix}_csn{i}") for i in range(4)]
        self.clock_csn = dmgr.get(f"{prefix}_csn4")
        self.adc_csn = [dmgr.get(f"{prefix}_csn{i+5}") for i in range(2)]
        
        try:
            self.trig = dmgr.get(f"{prefix}_trig")
        except Exception:
            pass
        
        self.clk0_ttl = dmgr.get(f"{prefix}_clk0_m2c_ttl_input")
        self.clk0_edge_counter = dmgr.get(f"{prefix}_clk0_m2c_edge_counter")
        self.clk1_ttl = dmgr.get(f"{prefix}_clk1_m2c_ttl_input")
        self.clk1_edge_counter = dmgr.get(f"{prefix}_clk1_m2c_edge_counter")

        self.adc0_lclk_ttl = dmgr.get(f"{prefix}_phy_adc0_lclk_input")
        self.adc0_lclk_edge_counter = dmgr.get(f"{prefix}_phy_adc0_lclk_counter")
        self.adc1_lclk_ttl = dmgr.get(f"{prefix}_phy_adc1_lclk_input")
        self.adc1_lclk_edge_counter = dmgr.get(f"{prefix}_phy_adc1_lclk_counter")

        

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

        self.idx_src_sel.on()
        for i in range(4):
            self.tdc_disable[i].off()
        delay(100*ns)
        for tdc in self.tdc:
            tdc.initialize()
        delay(10*ms)
        self.idx_in.pulse(1*us)
