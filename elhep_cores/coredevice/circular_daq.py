class CircularDaq:

    pass


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



class TDCGPX2ChannelDAQ:

    def __init__(self, dmgr, channel, data_width=44, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)
        self.data_width = data_width
        self.samples_msb = []
        self.samples_lsb = []
        self.samples = []

    @kernel
    def open_gate(self):
        rtio_output((self.channel << 8), 1)
        # delay_mu(self.ref_period_mu)  # FIXME: Do we need that?

    @kernel
    def close_gate(self):
        rtio_output((self.channel << 8), 0)
        # delay_mu(self.ref_period_mu)  # FIXME: Do we need that?

    @rpc(flags={"async"})
    def _store_sample(self, sample, msb):
        if msb:
            self.samples_msb.append(sample)
        else:
            self.samples_lsb.append(sample)

    @kernel
    def _transfer_from_rtio(self, msb) -> TInt32:
        i = 0
        ch = self.channel if msb else self.channel+1
        while True:
            ts, data = rtio_input_timestamped_data(10*ns, ch)
            if ts < 0:
                break
            else:
                self._store_sample([ts, data], msb)
                i += 1
        return i

    def get_samples(self):
        self._transfer_from_rtio(msb=True)
        if self.data_width > 32:
            self._transfer_from_rtio(msb=False)
            for lsb, msb in zip(self.samples_lsb, self.samples_msb):
                self.samples.append([msb[0], (msb[1] << 32) | (lsb[1])])
        else:
            self.samples = self.samples_msb