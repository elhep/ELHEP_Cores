def generate_signal(freq, fs, resolution=16, n_periods=100):
    n_samples = int(fs/freq*n_periods)
    t_stop = 1/fs*n_samples
    print(n_samples)
    T = np.linspace(0, t_stop, n_samples)
    S = 0.5*(np.sin(T)+1)*(2**resolution-1)
    return S


def run_for_signal(dut, sig):
    output = []
    for s in sig:
        yield dut.i.eq(int(s))
        output.append(dut.o)
        yield
        print(int(s), dut.o)


def testbench(dut, fs, cutoff):
    S1 = generate_signal(0.5 * cutoff, fs)
    S2 = generate_signal(2.0 * cutoff, fs)

    yield from run_for_signal(dut, S1)
    

