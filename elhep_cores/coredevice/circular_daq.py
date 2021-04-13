from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data, rtio_input_data
from artiq.language import TInt32, TInt64
from artiq.language.core import kernel, delay_mu, now_mu
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

        self.data_buffer = [int32(0)]*(1024)
        self.ts_buffer = [int64(0)]*(1024)
        
        self.data_mask = 2**data_width-1

    @kernel
    def configure_rt(self, pretrigger, posttrigger):
        rtio_output((self.channel << 8) | 0, pretrigger)
        delay_mu(self.ref_period_mu)
        rtio_output((self.channel << 8) | 1, posttrigger)
        delay_mu(self.ref_period_mu)
        self.pretrigger = pretrigger
        self.posttrigger = posttrigger

    @kernel
    def get_samples(self, timeout=100*ms):
        for idx in range(self.pretrigger+self.posttrigger):
            up_to = now_mu() + self.core.seconds_to_mu(timeout)
            timestamp, sample = rtio_input_timestamped_data(up_to, self.channel)
            if timestamp >= 0:
                self.data_buffer[idx] = sample
                self.ts_buffer[idx] = timestamp
            else:
                return idx
        return self.pretrigger+self.posttrigger

    @kernel
    def drain_channel(self):
        diff = self.core.seconds_to_mu(1*ms)
        ts, data = rtio_input_timestamped_data(now_mu()+diff, int32(self.channel))
        return ts

    @kernel
    def clear_fifo(self):
        ts = 0
        
        self.core.break_realtime()
        while ts >= 0:
            try:
                ts = self.drain_channel()
            except RTIOOverflow:
                pass

    @kernel
    def trigger(self):
        rtio_output((self.channel << 8) | 2, 1)
        delay_mu(self.ref_period_mu)