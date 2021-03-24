from artiq.coredevice import spi2 as spi
from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data
from artiq.language.core import kernel, rpc
from artiq.language.core import portable
from artiq.language.types import TInt32
from artiq.language.units import ns, us, ms
from elhep_cores.coredevice.rtlink_csr import RtlinkCsr
from artiq.coredevice.ttl import TTLOut
import re


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 1*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# Register 0

PIN_ENA1 = 1 << 0
PIN_ENA2 = 1 << 1
PIN_ENA3 = 1 << 2
PIN_ENA4 = 1 << 3

PIN_ENA_REFCLK = 1 << 4
PIN_ENA_LVDS_OUT = 1 << 5
PIN_ENA_DISABLE = 1 << 6
PIN_ENA_RSTIDX = 1 << 7

# Register 1

HIT_ENA1 = 1 << 0
HIT_ENA2 = 1 << 1
HIT_ENA3 = 1 << 2
HIT_ENA4 = 1 << 3

CHANNEL_COMBINE_NORMAL = 0b00 << 4
CHANNEL_COMBINE_PULSE_DISTANCE = 0b01 << 4
CHANNEL_COMBINE_PULSE_WIDTH = 0b10 << 4

HIGH_RESOLUTION_OFF = 0 << 6
HIGH_RESOLUTION_2x = 0b01 << 6
HIGH_RESOLUTION_4x = 0b10 << 6

# Register 2

class TDCGPX2:

    def __init__(self, dmgr, phy_csr_prefix, spi_device, chip_select, spi_freq=25_000_000, data_width=44, core_device="core"):
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        self.spi = dmgr.get(spi_device)
        self.chip_select = 0
        self.csn_device = dmgr.get(chip_select)
        self.div = self.spi.frequency_to_div(spi_freq)
        self.phy = [dmgr.get(f"{phy_csr_prefix}{i}") for i in range(4)]

        self.readout = [0] * 24

        self.regs = [
            ( 0, 0b10111111),  # All pins but DISABLE are enabled
            ( 1, 0b00001111),  # High res off, combine: independent channels, HIT_ENA on
            ( 2, 0b00111101),  # Block-wise FIFO off, common FIFO off, LVDS DDR, 20b stop, 24b ref idx
            # REFCLK period is 100ns (10MHz), to get 1ps divider must be 1000*100: 0b11000011010100000
            ( 3, 0b10100000),  # REFCLK_DIV lower 8bits
            ( 4, 0b10000110),  # REFCLK_DIV middle 8bits
            ( 5, 0b00000001),  # REFCLK_DIV upper 4bits
            ( 6, 0b11000000),  # test pattern disabled
            ( 7, 0b01010011),  # quartz disabled, LVDS data adjustment 0ps
            ( 8, 0b10100001),  # fixed value
            ( 9, 0b00010011),  # fixed value
            (10, 0b00000000),  # fixed value
            (11, 0b00001010),  # fixed value
            (12, 0b11001100),  # fixed value
            (13, 0b11001100),  # fixed value
            (14, 0b01111101),  # fixed value
            (15, 0b01111101),  # fixed value
            (16, 0b00000000),  # LVDS input level
        ]

    @kernel
    def write_op(self, op, end=False):
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            cs = 1
            delay(300*ns)

        if end:
            flags = SPI_CONFIG | spi.SPI_END
        else:
            flags = SPI_CONFIG

        self.spi.set_config_mu(flags, 8, self.div, cs)
        self.spi.write((op & 0xFF) << 24)

        if end and self.chip_select == 0:
            delay(300 * ns)
            self.csn_device.on()
            delay(10 * us)

    @kernel
    def write_data(self, data):
        self.spi.set_config_mu(SPI_CONFIG | spi.SPI_END, 8, self.div, 1)  # fixme: chip select
        self.spi.write((data & 0xFF) << 24)

    @kernel
    def read_rt(self, addr) -> TInt32:
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            cs = 1
            delay(50 * ns)

        self.spi.set_config_mu(SPI_CONFIG, 8, self.div, cs)
        self.spi.write(((0x40 | (addr & 0x1F)) << 24))
        self.spi.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, 8, self.div, cs)
        self.spi.write(0)

        if self.chip_select == 0:
            self.csn_device.on()
            delay(10 * us)

        return self.spi.read()

    @kernel
    def write_reg_rt(self, address, value):
        self.write_op(0x80 | address, end=False)
        delay(51*us)
        self.write_data(value & 0xFF)
        if self.chip_select == 0:
            delay(300 * ns)
            self.csn_device.on()

    @kernel
    def write_config_registers(self):
        self.write_op(0x80 | 0, end=False)
        delay(51*us)
        for r in self.regs:
            _, data = r
            self.write_data(data & 0xFF)
            delay(20800 * ns)

        if self.chip_select == 0:
            delay(300 * ns)
            self.csn_device.on()

        delay(100 * ns)

    @kernel
    def power_on_reset(self):
        self.write_op(0x30, end=True)

    @kernel
    def initialization_reset(self):
        self.write_op(0x18, end=True)

    @kernel
    def initialize(self):
        self.core.break_realtime()
        self.power_on_reset()
        delay(4*ms)
        self.write_config_registers()
        self.read_configuration()

        for a in range(17):
            re = self.readout[a]
            _, ro = self.regs[a]
            if re != ro:
                raise ValueError("TDC GPX-2: Invalid readout at address")

    @kernel
    def start_measurement(self):
        self.core.break_realtime()
        self.initialization_reset()

    @kernel
    def enable_lvds_test_pattern(self):
        self.core.break_realtime()
        self.write_reg_rt(6, 0b11010000)

    @kernel
    def disable_lvds_test_pattern(self):
        self.core.break_realtime()
        self.write_reg_rt(6, 0b11000000)

    @kernel
    def read_configuration(self):
        self.core.break_realtime()

        self.write_op(0x40, end=True)

        for i in range(24):
            self.readout[i] = self.read_rt(i)
        return self.readout





