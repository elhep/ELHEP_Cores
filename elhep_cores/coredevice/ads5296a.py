from artiq.coredevice import spi2 as spi
from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data, rtio_input_data
from artiq.language import TInt32, TInt64
from artiq.language.core import kernel, delay_mu
from artiq.language.core import rpc
from artiq.language.units import us, ns, ms
from coredevice.rtlink_csr import RtlinkCsr
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.exceptions import RTIOOverflow
from numpy import int64, int32


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


class AdcDaq:

    def __init__(self, dmgr, channel, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)
        self.pretrigger = 1024
        self.posttrigger = 1024
        self.incomplete = False
        self.samples = []

    @kernel
    def configure(self, pretrigger, posttrigger):
        rtio_output((self.channel << 8) | 1,
                    (pretrigger << 12) | posttrigger)
        delay_mu(self.ref_period_mu)
        self.pretrigger = pretrigger
        self.posttrigger = posttrigger

    @kernel
    def trigger(self):
        rtio_output((self.channel << 8) | 0, 0)  # data is not important, stb is used as a trigger
        # delay_mu(self.ref_period_mu)

    @rpc(flags={"async"})
    def store_sample(self, sample):
        self.samples.append(sample)

    @kernel
    def get_samples(self):
        self.incomplete = False
        for _ in range(self.pretrigger+self.posttrigger):
            timestamp, sample = rtio_input_timestamped_data(-1, self.channel)
            # self.core.seconds_to_mu(10000*us)
            if timestamp >= 0:
                self.store_sample(sample)
            else:
                print(_)
                raise ValueError("DAQ incomplete data")

    @kernel
    def clear_fifo(self):
        ts = 0
        while ts >= 0:
            ts, data = rtio_input_timestamped_data(int64(100), int32(self.channel))


class ADS5296A:

    def __init__(self, dmgr, channel, spi_device, chip_select, spi_freq=10_000_000, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        if isinstance(spi_device, str):
            self.spi = dmgr.get(spi_device)
        else:
            self.spi = spi_device  # type: spi.SPIMaster
        self.chip_select = chip_select

        self.div = self.spi.frequency_to_div(spi_freq)

        if isinstance(chip_select, TTLOut):
            self.chip_select = 0
            self.csn_device = chip_select
        else:
            self.chip_select = chip_select
            self.csn_device = None

        phy_config = [
            [0, "data0_delay_value", 5],
            [1, "data1_delay_value", 5],
            [2, "data2_delay_value", 5],
            [3, "data3_delay_value", 5],
            [4, "data4_delay_value", 5],
            [5, "data5_delay_value", 5],
            [6, "data6_delay_value", 5],
            [7, "data7_delay_value", 5],
            [8, "data8_delay_value", 5],
            [9, "adclk_delay_value", 5],
            [10, "phy_reset", 1],
            [11, "bitslip_done", 1]
        ]

        self.phy = RtlinkCsr(dmgr, channel, config=phy_config, core_device=core_device)
        self.daq = [AdcDaq(dmgr, channel+1+i, core_device) for i in range(9)]

    @kernel
    def write(self, addr, data):
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            delay(40 * ns)
            cs = 1

        self.spi.set_config_mu(SPI_CONFIG | spi.SPI_END, 24, self.div, cs)
        self.spi.write((((addr & 0xFF) << 16) | (data & 0xFFFF)) << 8)

        if self.chip_select == 0:
            self.csn_device.on()
        delay(100 * ns)

    @kernel
    def enable_read(self):
        self.write(0x1, 0x1)

    @kernel
    def disable_read(self):
        self.write(0x1, 0x0)

    @kernel
    def read(self, addr) -> TInt32:
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            delay(40 * ns)
            cs = 1

        self.spi.set_config_mu(SPI_CONFIG, 8, self.div, cs)
        self.spi.write((addr & 0xFF) << 24)
        self.spi.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, 16, self.div, cs)
        self.spi.write(0)

        if self.chip_select == 0:
            self.csn_device.on()
        delay(100 * ns)

        return self.spi.read()

    @kernel
    def enable_test_pattern(self, pattern):
        self.core.break_realtime()
        self.write(0x26, (pattern & 0xFF) << 8)
        self.write(0x25, 1 << 4 | ((pattern >> 8) & 0x3))
   
    @kernel
    def enable_ramp_test_pattern(self):
        self.core.break_realtime()
        self.write(0x25, 1 << 6)

    @kernel
    def disable_test_pattern(self):
        self.core.break_realtime()
        self.write(0x25, 0)

    @kernel
    def test_spi(self):
        self.write(0xA, 0xF00F)
        self.enable_read()
        r = self.read(0xA)
        delay(100 * us)
        self.disable_read()
        if r != 0xF00F:
            raise ValueError("ADS5269: Invalid readout")

    @kernel
    def initialize(self):
        self.core.break_realtime()
        self.phy.phy_reset.write_rt(1)
        delay(5*ms)
        self.test_spi()
        # self.write(0x1C, 1 << 14 | (0x3e0))
        self.write(0x46, 0x8100 | (1<<3))
        # delay(10*ms)
        self.phy.phy_reset.write_rt(0)



        
