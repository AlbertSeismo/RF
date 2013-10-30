from numpy import max, pi
from obspy.signal.util import nextpow2
from scipy.fftpack import fft, ifft
from scipy.signal import correlate
from toeplitz import sto_sl
import numpy as np

def deconv(stream, src_comp, method='time', **kwargs):
    """
    Deconvolve one component of a stream from all components

    The deconvolutions are written to the data arrays of the stream. To keep
    the original data use the copy method of Stream.
    The stats dictionaries of the traces inside stream must have an 'onset'
    entry with a :class:`~obspy.core.UTCDateeTime` object. This will be used
    for determining the data windows.

    :param stream: :class:`~obspy.Stream` object including response and source
    :param src_comp: Name of component using for source function
    :param method: 'time' -> use time domain deconvolution
        :func:`~rf.deconvolve.deconvt`
        'freq' -> use freqeuency domain deconvolution
        :func:`~rf.deconvolve.deconvf`, optional
    :param winsrc: data window for source function, tuple with
        (start, end, taper) in seconds relative to onset, optional, default:
        (-10, 30, 5) for method='time', (-20, 80, 5) for method='freq'
    :param winrsp: data window for response functions, tuple (start, end),
        optional, just for method='time', default: (-20, 80)
    :param winrf: data window for results/ deconvolution/receiver functions,
        optional, just for method='time', default: (-20, 80)
    Other optional parameters are passed to the underlying deconvolution
    functions :func:`~rf.deconvolve.deconvt` and :func:`~rf.deconvolve.deconvf`.
    """
    if method not in ('time', 'freq'):
        raise NotImplementedError()
    if method == 'time':
        winsrc = kwargs.get('winsrc', (-10, 30, 5))
        winrsp = kwargs.get('winrsp', (-20, 80))
        winrf = kwargs.get('winrf', (-20, 80))
    else:
        winsrc = kwargs.get('winsrc', (-20, 80, 5))
        tshift = kwargs.get('tshift', 10)
    st = stream
    samp = st[0].stats.sampling_rate
    onset = st[0].stats.onset
    src = st.select(component=src_comp)[0]
    src_index = st.traces.index(src)
    src = src.copy()
    src.trim(onset + winsrc[0], onset + winsrc[1])
    src.taper(max_percentage=None, max_length=winsrc[2])
    src = src.data
    rsp = [st[(i + src_index) % 3].data for i in range(3)]
    if method == 'time':
        time_rf = winrf[1] - winrf[0]
        shift = int(samp * ((winrsp[1] - winrsp[0] - winsrc[1] + winsrc[0] -
                         time_rf) / 2 + winrsp[0] - winsrc[0] - winrf[0]))
        length = int(time_rf * samp)
        rf_resp = deconvt(rsp, src, shift, length=length, **kwargs)
        tshift = -winrf[0]
    else:
        rf_resp = deconvf(rsp, src, samp, **kwargs)
    for i in range(3):
        st[(i + src_index) % 3].data = rf_resp[i].real
    for tr in st:
        tr.stats.tshift = tshift

def deconvf(rsp_list, src, sampling_rate, water=0.05, gauss=2., tshift=10.,
            pad=0, length=None, normalize=True, normalize_to_src=False,
            return_dict=False):
    """
    Frequency-domain deconvolution using waterlevel method.

    Deconvolve src from arrays in rsp_list.

    :param rsp_list: either a list of arrays containing the response functions
        or a single array
    :param src: array of source function
    :param sampling_rate: sampling rate of the data
    :param water: waterlevel to stabilize the deconvolution, optional
    :param gauss: Gauss parameter of Low-pass filter, optional
    :param tshift: delay time 0s will be at time tshift afterwards, optional
    :param pad: multiply number of samples used for fft by 2**pad, optional
    :param length: number of data points in results, optional
    :param normalize: if results are normalized, optional
    :param normalize_to_src: True ->  normalized so that the maximum of a
        deconvolution of the source with itself is 1
        False -> normalized so that the maximum of the deconvolution of the
        first response array in rsp_list is 1, optional
    :param return_dict: return additionally a lot of different parameters in a
        dict for debugging purposes, optional

    :return: (list of) array(s) with deconvolution(s)
    """
    if length == None:
        length = len(src)
    N = length
    nfft = nextpow2(N) * 2 ** pad
    freq = np.fft.fftfreq(nfft, d=1. / sampling_rate)
    gauss = np.exp(np.maximum(-(0.5 * 2 * pi * freq / gauss) ** 2, -700.) -
                   1j * tshift * 2 * pi * freq)

    spec_src = fft(src, nfft)
    spec_src_conj = np.conjugate(spec_src)
    spec_src_water = np.abs(spec_src * spec_src_conj)
    spec_src_water = np.maximum(spec_src_water, max(spec_src_water) * water)

    if normalize_to_src:
        spec_src = gauss * spec_src * spec_src_conj / spec_src_water
        rf_src = ifft(spec_src, nfft)[:N]
        norm = 1 / max(rf_src)
        rf_src = norm * rf_src

    flag = False
    if not isinstance(rsp_list, (list, tuple)):
        flag = True
        rsp_list = [rsp_list]
    rf_list = [ifft(gauss * fft(rsp, nfft) * spec_src_conj / spec_src_water,
                    nfft)[:N] for rsp in rsp_list]
    if normalize:
        if not normalize_to_src:
            norm = 1. / max(rf_list[0])
        for rf in rf_list:
            rf *= norm
    if return_dict:
        if not normalize_to_src:
            spec_src = gauss * spec_src * spec_src_conj / spec_src_water
            rf_src = ifft(spec_src, nfft)[:N]
            norm = 1 / max(rf_src)
            rf_src = norm * rf_src
        ret_dict = {'rf_src': rf_src, 'rf_src_conj': spec_src_conj,
                    'spec_src_water': spec_src_water, 'freq':freq,
                    'gauss':gauss, 'norm': norm, 'N':N, 'nfft':nfft}
        return rf_list, ret_dict
    elif flag:
        return rf
    else:
        return rf_list

def add_zeros(a, num, side='both'):
    """Add 'num' zeros at 'side' side of array a"""
    return np.hstack([np.zeros(num)] * (side in ('both', 'left')) + [a] +
                     [np.zeros(num)] * (side in ('both', 'right')))

def acorrt(a, num):
    """
    Return not normalized auto-correlation of signal a.

    Sample 0 corresponds to zero lag time. Auto-correlation will consist of
    num samples.
    """
    return correlate(add_zeros(a, num, 'right'), a, 'valid')

def xcorrt(a, b, num, zero_sample=0):
    """
    Return not normalized cross-correlation of signals a and b.

    zero_sample: Signals a and b are aligned around the middle of their signals.
                 If zero_sample != 0 a will be shifted additionally to the left.
    num: The cross-correlation will consist of 2*num+1 samples. The sample with
         0 lag time will be in the middle.
    """
    if zero_sample != 0:
        a = add_zeros(a, 2 * abs(zero_sample),
                      'left' if zero_sample > 0 else 'right')
    dif = len(a) - len(b) - 2 * num
    if dif > 0:
        b = add_zeros(b, dif // 2)
    else:
        a = add_zeros(a, -dif // 2)
    return correlate(a, b, 'valid')

def toeplitz_real_sym(a, b):
    """
    Solve linear system Ax=b for real symmetric Toeplitz matrix A

    a   first row of Toeplitz matrix A
    b   vector
    """
    return sto_sl(np.hstack((a, a[1:])), b, job=0)

# Gives similar results as a deconvolution with Seismic handler,
# but SH is faster
def deconvt(rsp_list, src, shift, spiking=1., length=None, normalize=True):
    """
    Time domain deconvolution.

    Deconvolve src from arrays in rsp_list.
    Calculate Toeplitz auto-correlation matrix of source, invert it, add noise
    and multiply it with cross-correlation vector of response and source.

    In a formula:
    RF = (STS + spiking*I)^-1 * STR
    This function calculates RF.

    N... length
        ( S0   S-1  S-2 ... S-N+1 )
        ( S1   S0   S-1 ... S-N+2 )
    S = ( S2   ...                )
        ( ...                     )
        ( SN-1 ...          S0    )
    R = (R0 R1 ... RN-1)^T
    RF = (RF0 RF1 ... RFN-1)^T
    S... source matrix (shape N*N)
    R... response vector (length N)
    RF... receiver function (deconvolution) vector (length N)
    STS = S^T*S = symetric Toeplitz autocorrelation matrix
    STR = S^T*R = cross-correlation vector
    I... Identity

    :param rsp_list: either a list of arrays containing the response functions
        or a single array
    :param src: array of source function
    :param shift: shift the source by that amount of samples to the left side
        to get onset in RF at the desired time (negative -> shift source to the
        right side)
        shift = (middle of rsp window - middle of src window) +
                (0 - middle rf window)
    :param spiking: random noise added to autocorrelation (eg. 1.0, 0.1), optional
    :param length: number of data points in results, optional
    :param normalize: normalize all results so that the maximum of the first
        result is 1

    :return: (list of) array(s) with deconvolution(s)
    """
    if length == None:
        length = len(src)
    flag = False
    RF_list = []
    STS = acorrt(src, length)
    STS = STS / STS[0]
    STS[0] += spiking
    if not isinstance(rsp_list, (list, tuple)):
        flag = True
        rsp_list = [rsp_list]
    for rsp in rsp_list:
        STR = xcorrt(rsp, src, length // 2, shift)
        if len(STR) > len(STS):
            STR = np.delete(STR, -1)
        RF = toeplitz_real_sym(STS, STR)
        RF_list.append(RF)
    if normalize:
        norm = 1 / np.max(np.abs(RF_list[0]))
        for RF in RF_list:
            RF *= norm
    if flag:
        return RF
    else:
        return RF_list
