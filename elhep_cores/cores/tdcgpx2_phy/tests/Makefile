VERILOG_SOURCES = $(XILINX_VIVADO)/data/verilog/src/glbl.v sim_build/dut.v
TOPLEVEL=top
MODULE=tb_tdcgpx2

COMPILE_ARGS=-y$(XILINX_VIVADO)/data/verilog/src/unisims -s glbl

ELHEP_CORES=$(PWD)/../../../..
DARTIQ_IMAGE=dartiq

export PYTHONPATH := $(PYTHONPATH):$(ELHEP_CORES)

include $(shell cocotb-config --makefiles)/Makefile.sim

sim_build/dut.v: $(PWD)/../tdcgpx2.py $(PWD)/../../xilinx.py
	mkdir -p sim_build
	dartiq run -m $(PWD)/../../../.. --workspace=sim_build/ --image=$(DARTIQ_IMAGE) "python -m elhep_cores.cores.tdcgpx2_phy.tdcgpx2"