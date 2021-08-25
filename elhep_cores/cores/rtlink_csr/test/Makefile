VERILOG_SOURCES = $(XILINX_VIVADO)/data/verilog/src/glbl.v sim_build/dut.v
TOPLEVEL=top
MODULE=tb_rtlink_csr

# SIM=icarus
COMPILE_ARGS=-y$(XILINX_VIVADO)/data/verilog/src/unisims -s glbl

ELHEP_CORES=$(PWD)/../../../..
DARTIQ_IMAGE=dartiq

export PYTHONPATH := $(PYTHONPATH):$(ELHEP_CORES)

include $(shell cocotb-config --makefiles)/Makefile.sim

sim_build/dut.v: $(PWD)/../../rtlink_csr.py 
	mkdir -p sim_build
	dartiq run -m $(PWD)/../../../.. --workspace=sim_build/ --no-stdin --image=$(DARTIQ_IMAGE) "python -m elhep_cores.cores.rtlink_csr"