VERILOG_SOURCES=$(XILINX_VIVADO)/data/verilog/src/glbl.v sim_build/dut.v
TOPLEVEL=top
TOPLEVEL_LANG=verilog
MODULE=tb_ads5296a_xs7
SIM=questa
WAVES=1

SIM_ARGS=-voptargs=\"-L unisims_ver -L unimacro_ver -L secureip\" work.glbl

ELHEP_CORES=$(PWD)/../../../..
DARTIQ_IMAGE=dartiq

export PYTHONPATH := $(PYTHONPATH):$(ELHEP_CORES)

include $(shell cocotb-config --makefiles)/Makefile.sim

sim_build/dut.v: $(PWD)/../ads5296a.py $(PWD)/../../xilinx.py
	mkdir -p sim_build
	dartiq run -m $(PWD)/../../../.. --workspace=sim_build/ --image=$(DARTIQ_IMAGE) "python -m elhep_cores.cores.ads5296a_phy.ads5296a"
