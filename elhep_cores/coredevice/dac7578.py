class DAC7578:

    def __init__(self, dmgr, address, busno=0, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address