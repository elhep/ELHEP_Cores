import os

from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.interconnect import stream
from misoc.cores.liteeth_mini.common import *


class Open(Signal): pass

class AfckPCSPMA(Module):
    dw          = 8
    tx_clk_freq = 125e6
    rx_clk_freq = 125e6

    def __init__(self, platform, clk_pads, data_pads, sys_clk_freq, cd_idelayctrl="idelay"):
        self.clock_domains.cd_eth_tx      = ClockDomain()
        self.clock_domains.cd_eth_rx      = ClockDomain()
        
        self.sink = stream.Endpoint(eth_phy_layout(8))
        self.source = stream.Endpoint(eth_phy_layout(8))
        self.link_up = Signal()

        # # #

        assert sys_clk_freq == 125e6

        gmii_clock = Signal()
        mmcm_locked = Signal()
        self.comb += [
            self.sink.ack.eq(1),
            self.cd_eth_tx.clk.eq(gmii_clock),
            self.cd_eth_rx.clk.eq(gmii_clock),
        ]
        self.specials += AsyncResetSynchronizer(self.cd_eth_tx, ~mmcm_locked)
        self.specials += AsyncResetSynchronizer(self.cd_eth_rx, ~mmcm_locked)
        
        status = Signal(16)
        self.comb += self.link_up.eq(status[0])
        
        data_rx = Signal(8)
        data_rx_d = Signal(8)
        data_valid = Signal()
        data_valid_d = Signal()
        self.sync.eth_rx += [
            self.source.eop.eq(~data_valid & data_valid_d),
            self.source.data.eq(data_rx_d),
            data_rx_d.eq(data_rx),
            self.source.stb.eq(data_valid_d),
            data_valid_d.eq(data_valid),
        ]
   
        parameters = {
            "i_gtrefclk_p": clk_pads.p,
            "i_gtrefclk_n": clk_pads.n,
            "o_gtrefclk_out": Open(),
            "o_gtrefclk_bufg_out": Open(),
      
            "o_txp": data_pads.txp,
            "o_txn": data_pads.txn,
            "i_rxp": data_pads.rxp,
            "i_rxn": data_pads.rxn,
      
            "o_mmcm_locked_out": mmcm_locked,
      
            "o_userclk_out": Open(),
            "o_userclk2_out": gmii_clock,
            "o_rxuserclk_out": Open(),
            "o_rxuserclk2_out": Open(),
            "i_independent_clock_bufg": ClockSignal(cd_idelayctrl),
            "o_pma_reset_out": Open(),
            "o_resetdone": Open(),
      
            "o_sgmii_clk_r": Open(),
            "o_sgmii_clk_f": Open(),
            "o_sgmii_clk_en": Open(),
            "i_gmii_txd": self.sink.data,
            "i_gmii_tx_en": self.sink.stb,
            "i_gmii_tx_er": 0,
            "o_gmii_rxd": data_rx,
            "o_gmii_rx_dv": data_valid,
            "o_gmii_rx_er": Open(),
            "i_gmii_isolate": 0,
            "i_configuration_vector": 0b10000,
            "o_an_interrupt": Open(),
            "i_an_adv_config_vector": 0x01a0,
            "i_an_restart_config": 0,
            "i_basex_or_sgmii": 0,
            "i_speed_is_10_100": 0,
            "i_speed_is_100": 0,
            "o_status_vector": status,
            "i_reset": ResetSignal(),

            "i_signal_detect": 1,
            "o_gt0_qplloutclk_out": Open(),
            "o_gt0_qplloutrefclk_out": Open()
        }
        platform.add_ip(os.path.join(os.path.abspath(os.path.dirname(__file__)), "afck_pcspma.xci"))
        self.specials += Instance("afck_pcspma", **parameters)
