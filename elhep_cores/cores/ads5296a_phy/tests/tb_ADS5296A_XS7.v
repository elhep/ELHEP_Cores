`timescale 1ns/1ps

module tb_ADS5296A_XS7 ();

    reg adclk_i_p = 1'd0;
    reg adclk_i_n = 1'd1;
    reg lclk_i_p = 1'd0;
    reg lclk_i_n = 1'd1;
    reg dat_0_i_p;
    reg dat_0_i_n;
    reg dat_1_i_p;
    reg dat_1_i_n;
    reg dat_2_i_p;
    reg dat_2_i_n;
    reg dat_3_i_p;
    reg dat_3_i_n;
    reg dat_4_i_p;
    reg dat_4_i_n;
    reg dat_5_i_p;
    reg dat_5_i_n;
    reg dat_6_i_p;
    reg dat_6_i_n;
    reg dat_7_i_p;
    reg dat_7_i_n;
    reg sys_clk = 1'd0;
    reg [4:0] idelay_val_0_i;
    reg [4:0] idelay_val_1_i;
    reg [4:0] idelay_val_2_i;
    reg [4:0] idelay_val_3_i;
    reg [4:0] idelay_val_4_i;
    reg [4:0] idelay_val_5_i;
    reg [4:0] idelay_val_6_i;
    reg [4:0] idelay_val_7_i;
    reg [4:0] idelay_val_8_i;
    reg idelay_ld_i;
    
    reg sys_rst = 1'd1;
    reg rst_i = 1'd1;
    reg ref_clk_200M = 1'd0;

    wire data_clk_o;
    wire bitslip_done;
    wire [9:0] data_0_o;
    wire [9:0] data_1_o;
    wire [9:0] data_2_o;
    wire [9:0] data_3_o;
    wire [9:0] data_4_o;
    wire [9:0] data_5_o;
    wire [9:0] data_6_o;
    wire [9:0] data_7_o;

    top DUT (
        .adclk_i_p (adclk_i_p),
        .adclk_i_n (adclk_i_n),
        .lclk_i_p (lclk_i_p),
        .lclk_i_n (lclk_i_n),
        .dat_0_i_p (dat_0_i_p),
        .dat_0_i_n (dat_0_i_n),
        .dat_1_i_p (dat_1_i_p),
        .dat_1_i_n (dat_1_i_n),
        .dat_2_i_p (dat_2_i_p),
        .dat_2_i_n (dat_2_i_n),
        .dat_3_i_p (dat_3_i_p),
        .dat_3_i_n (dat_3_i_n),
        .dat_4_i_p (dat_4_i_p),
        .dat_4_i_n (dat_4_i_n),
        .dat_5_i_p (dat_5_i_p),
        .dat_5_i_n (dat_5_i_n),
        .dat_6_i_p (dat_6_i_p),
        .dat_6_i_n (dat_6_i_n),
        .dat_7_i_p (dat_7_i_p),
        .dat_7_i_n (dat_7_i_n),

        .data_clk_o (data_clk_o),
        .bitslip_done (bitslip_done),
        .data_0_o (data_0_o),
        .data_1_o (data_1_o),
        .data_2_o (data_2_o),
        .data_3_o (data_3_o),
        .data_4_o (data_4_o),
        .data_5_o (data_5_o),
        .data_6_o (data_6_o),
        .data_7_o (data_7_o),
        
        .sys_clk (sys_clk),
        .sys_rst (sys_rst),
        .rst_i (rst_i),
        .ref_clk_200M (ref_clk_200M),
        .idelay_val_0_i (idelay_val_0_i),
        .idelay_val_1_i (idelay_val_1_i),
        .idelay_val_2_i (idelay_val_2_i),
        .idelay_val_3_i (idelay_val_3_i),
        .idelay_val_4_i (idelay_val_4_i),
        .idelay_val_5_i (idelay_val_5_i),
        .idelay_val_6_i (idelay_val_6_i),
        .idelay_val_7_i (idelay_val_7_i),
        .idelay_val_8_i (idelay_val_8_i),
        .idelay_ld_i (idelay_ld_i)
    );

    parameter SAMPLE_PERIOD = 10;
    parameter CLK_PERIOD = SAMPLE_PERIOD/5.0;

    always #(SAMPLE_PERIOD/2.0/5.0) lclk_i_p = ~lclk_i_p;
    always #(SAMPLE_PERIOD/2.0/5.0) lclk_i_n = ~lclk_i_n;
    
    always #(2.5) ref_clk_200M = ~ref_clk_200M;
    
    always #4.0 sys_clk = ~sys_clk;

    task automatic generate_frame (ref fp, fn);
    begin
        fp = 1;
        fn = 0;
        #(SAMPLE_PERIOD/2.0);
        fp = 0;
        fn = 1;
        #(SAMPLE_PERIOD/2.0);
    end
    endtask
    
    task automatic generate_data (input [9:0] data, ref dp, dn);
        integer i;
    begin
        i = 9;        
        while (i > 0) begin
            dp =  data[i];
            dn = ~data[i];
            #(CLK_PERIOD/2.0);
            dp =  data[i-1];
            dn = ~data[i-1];
            i = i-2;
            #(CLK_PERIOD/2.0);
        end
    end
    endtask

    task automatic transfer_frame (input integer i);
    begin
        fork
            #100 generate_frame(adclk_i_p, adclk_i_n);
            #20 generate_data(i, dat_0_i_p, dat_0_i_n);
            generate_data(i+1, dat_1_i_p, dat_1_i_n);
            generate_data(i+3, dat_2_i_p, dat_2_i_n);
            generate_data(i+5, dat_3_i_p, dat_3_i_n);
            generate_data(i+7, dat_4_i_p, dat_4_i_n);
            generate_data(i+11, dat_5_i_p, dat_5_i_n);
            generate_data(i+13, dat_6_i_p, dat_6_i_n);
            generate_data(i+17, dat_7_i_p, dat_7_i_n);
        join
    end;
    endtask;

    task automatic verify_data ( input integer i);
    begin
        assert (data_0_o == i) else $error("Invalid data on data_0_o! (%d != %d)", i, data_0_o);
        assert (data_1_o == i+1) else $error("Invalid data on data_1_o! (%d != %d)", i, data_1_o);
        assert (data_2_o == i+3) else $error("Invalid data on data_2_o! (%d != %d)", i, data_2_o);
        assert (data_3_o == i+5) else $error("Invalid data on data_3_o! (%d != %d)", i, data_3_o);
        assert (data_4_o == i+7) else $error("Invalid data on data_4_o! (%d != %d)", i, data_4_o);
        assert (data_5_o == i+11) else $error("Invalid data on data_5_o! (%d != %d)", i, data_5_o);
        assert (data_6_o == i+13) else $error("Invalid data on data_6_o! (%d != %d)", i, data_6_o);
        assert (data_7_o == i+17) else $error("Invalid data on data_7_o! (%d != %d)", i, data_7_o);
    end;
    endtask
    
    task automatic initialize ( );
    begin
        // Initialize inputs with some reasonable values
        dat_0_i_p = 0;
        dat_0_i_n = 1;
        dat_1_i_p = 0;
        dat_1_i_n = 1;
        dat_2_i_p = 0;
        dat_2_i_n = 1;
        dat_3_i_p = 0;
        dat_3_i_n = 1;
        dat_4_i_p = 0;
        dat_4_i_n = 1;
        dat_5_i_p = 0;
        dat_5_i_n = 1;
        dat_6_i_p = 0;
        dat_6_i_n = 1;
        dat_7_i_p = 0;
        dat_7_i_n = 1;
        idelay_ld_i = 1'd0;
        idelay_val_0_i = 0;
        idelay_val_1_i = 0;
        idelay_val_2_i = 0;
        idelay_val_3_i = 0;
        idelay_val_4_i = 0;
        idelay_val_5_i = 0;
        idelay_val_6_i = 0;
        idelay_val_7_i = 0;
        idelay_val_8_i = 0;
        sys_rst = 1'd1;
        rst_i = 1'd1;
        
        // Wait for GSR to be low (takes 100 ns)
        #200;

        // Disable reset signals
        sys_rst = 1'd0;
        rst_i = 1'd0;
    end;
    endtask
        
    initial begin
    
        initialize();
        
        
        
        
        // Wait at least 2 CLKDIV (aka SAMPLE_CLOCK)
        #(4.0*SAMPLE_PERIOD); 

        // Set appropriate relation to lclk_i_p
        @(negedge lclk_i_p);
        #(SAMPLE_PERIOD/4.0);

        // Send some data to start alignement process
        for(int i=0; i<10; i++) transfer_frame(0);
        assert (bitslip_done) else $error("Alignment failure!");

        transfer_frame(0);
        for(int i=1; i<1024-17; i++) begin
            $display("Transfering frame with seed %d", i);
            transfer_frame(i);
            verify_data(i-1);
        end;
     
        $finish;
    end

endmodule
