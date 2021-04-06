from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data, rtio_input_data
from artiq.language import TInt32, TInt64
from artiq.language.core import kernel, delay_mu
from artiq.language.core import rpc
from artiq.language.units import us, ns, ms
from elhep_cores.coredevice.rtlink_csr import RtlinkCsr
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.exceptions import RTIOOverflow
from numpy import int64, int32


class CircularDaq:

    def __init__(self, dmgr, channel, data_width, trigger_cnt_width, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)
        self.pretrigger = 100
        self.posttrigger = 100
        self.data_width = data_width
        self.trigger_cnt_width = trigger_cnt_width
        self.incomplete = False
        self.samples = []

        self.data_mask = 2**data_width-1

    @kernel
    def configure(self, pretrigger, posttrigger):
        rtio_output((self.channel << 8) | 0, pretrigger)
        delay_mu(self.ref_period_mu)
        rtio_output((self.channel << 8) | 1, posttrigger)
        delay_mu(self.ref_period_mu)
        self.pretrigger = pretrigger
        self.posttrigger = posttrigger

    @rpc(flags={"async"})
    def store_sample(self, sample):
        data = sample & self.data_mask
        trigger_cnt = sample >> self.data_width
        self.samples.append((trigger_cnt, data))

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

    @kernel
    def trigger(self):
        rtio_output((self.channel << 8) | 2, 1)
        delay_mu(self.ref_period_mu)