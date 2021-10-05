VERILOG_SOURCES = $(XILINX_VIVADO)/data/verilog/src/glbl.v sim_build/dut.v
TOPLEVEL=top
MODULE=tb_IntegralRT
COMPILE_ARGS=-y$(XILINX_VIVADO)/data/verilog/src/unisims -s glbl

SIM=icarus

ELHEP_CORES=$(PWD)/../../../..
DARTIQ_IMAGE=dartiq

include $(shell cocotb-config --makefiles)/Makefile.sim

sim_build/dut.v: $(PWD)/../IntegralRT.py $(PWD)/../integral.py
	mkdir -p sim_build
	dartiq run -m $(ELHEP_CORES) --workspace=sim_build/ --image=$(DARTIQ_IMAGE) "python -m elhep_cores.cores.integral.IntegralRT"
