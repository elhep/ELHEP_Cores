import re

from artiq.coredevice import spi2 as spi
from artiq.coredevice.ttl import TTLOut
from artiq.language.core import kernel
from artiq.language.units import *
from numpy import int32


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


class AD9528:

    def __init__(self, dmgr, spi_device, chip_select, reset_device=None, spi_freq=10_000_000, config=None,
                 core_device="core"):
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        self.reset_device = reset_device

        if isinstance(spi_device, str):
            self.spi = dmgr.get(spi_device)
        else:
            self.spi = spi_device  # type: spi.SPIMaster

        if isinstance(chip_select, TTLOut):
            self.chip_select = 0
            self.csn_device = chip_select
        else:
            self.chip_select = chip_select
            self.csn_device = None

        self.div = self.spi.frequency_to_div(spi_freq)

        self.regs = []
        if config:
            self._parse_config_string(config)

        self.config_readout = [0]*len(self.regs)

    def _parse_config_string(self, r):
        r = r.strip()
        r = r.split('\n')

        self.regs = []
        for rr in r[1:]:
            self.regs.append([int32(int(x.strip(), 16)) for x in rr.split(',')[:-1]])

    @kernel
    def reset(self):
        self.write(0, 0b10000001)
        delay(10 * us)
        self.write(0, 0x3C)

    @kernel
    def write_config_regs(self):
        for r in self.regs:
            self.write(r[0], r[1])
        self.write(0xF, 1)
        delay(10 * us)

    @kernel
    def read_config_regs(self):
        for i in range(len(self.regs)):
            readout = self.read(self.regs[i][0])
            self.config_readout[i] = readout
            delay(10 * us)

    @kernel
    def update_registers(self):
        self.write(0xF, 1)

    @kernel
    def write(self, addr, data):
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            delay(40 * ns)
            cs = 1

        self.spi.set_config_mu(flags=SPI_CONFIG | spi.SPI_END, length=24, div=self.div, cs=cs)
        self.spi.write(((0 << 15) | ((addr & 0x7FFF) << 8) | (data & 0xFF)) << 8)

        if self.chip_select == 0:
            self.csn_device.on()
        delay(100 * ns)

    @kernel
    def read(self, addr):
        cs = self.chip_select
        if self.chip_select == 0:
            self.csn_device.off()
            delay(50 * ns)
            cs = 1

        self.spi.set_config_mu(flags=SPI_CONFIG, length=16, div=self.div, cs=cs)
        self.spi.write(((1 << 15) | (addr & 0x7FFF)) << 16)

        self.spi.set_config_mu(flags=SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, length=8, div=self.div, cs=cs)
        self.spi.write(0)
        delay(50 * ns)

        if self.chip_select == 0:
            self.csn_device.on()
        delay(100 * ns)

        return self.spi.read()

    @kernel
    def initialize(self):
        # Let's have a known starting point
        self.reset()
        # Configure according to data given at initalization
        self.write_config_regs()
        # Verify configuration
        self.read_config_regs()
        for idx in range(len(self.regs)):
            r = self.regs[idx]
            ro = self.config_readout[idx]
            if r[0] >= 0x505:
                continue
            if r[1] != ro:
                raise ValueError("AD9528: Invalid readout")
        # Verify VCXO status
        sreg0, sreg1 = self.get_status_mu()
        if not (sreg0 & (1 << 5)):
            raise ValueError("AD9528: VCXO missing")

    @kernel
    def get_status_mu(self):
        self.core.break_realtime()
        sreg0 = self.read(0x0508)
        delay(1*ms)
        sreg1 = self.read(0x0509)
        return sreg0, sreg1

    def get_status(self):
        sreg0, sreg1 = self.get_status_mu()

        return {
            "pll2_status": bool(sreg0 & (1 << 7)),
            "pll1_status": bool(sreg0 & (1 << 6)),
            "vcxo_status": bool(sreg0 & (1 << 5)),
            "both_ref_missing": bool(sreg0 & (1 << 4)),
            "refb_status": bool(sreg0 & (1 << 3)),
            "refa_status": bool(sreg0 & (1 << 2)),
            "pll2_locked": bool(sreg0 & (1 << 1)),
            "pll1_locked": bool(sreg0 & (1 << 0)),

            "holdover_active": bool(sreg1 & (1 << 3)),
            "selected_reference": "refa" if sreg1 & (1 << 2) else "refb",
            "fast_lock_in_progress": bool(sreg1 & (1 << 1)),
            "vco_calib_busy": bool(sreg1 & (1 << 0)),
        }

