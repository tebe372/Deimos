import spextractor as spx
from os.path import *
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import argparse


plt.switch_backend('agg')


def main(exp_path, output_path, beta, tfix, ms1_threshold, ms2_threshold):
    # output directory
    if not exists(output_path):
        os.makedirs(output_path)

    # calibrate
    c = spx.calibrate.ArrivalTimeCalibration()
    c.calibrate(tfix=tfix, beta=beta)

    # load
    data = spx.utils.load_hdf(exp_path)

    # split by ms level
    ms1 = data.loc[data['ms_level'] == 1, :].drop('ms_level', axis=1)
    ms2 = data.loc[data['ms_level'] == 2, :].drop('ms_level', axis=1)

    # find features
    ms1_peaks = spx.peakpick.auto(ms1, features=['mz', 'drift_time'],
                                  res=[0.01, 0.12], sigma=[0.03, 0.3], truncate=4, threshold=ms1_threshold)

    # container
    d = {'mz': [], 'dt': [], 'ccs': [], 'intensity': [], 'ms2': []}
    d_centroid = {'mz': [], 'dt': [], 'ccs': [], 'intensity': [], 'ms2': []}

    # iterate through peaks
    for idx, peak in ms1_peaks.iterrows():
        mz_exp = peak['mz']
        dt_exp = peak['drift_time']
        int_exp = peak['intensity']
        ccs_exp = c.arrival2ccs(dt_exp, mz_exp)

        # extract ms2
        ms2_subset = spx.targeted.find_feature(ms2,
                                               by='drift_time',
                                               loc=dt_exp,
                                               tol=4 * 0.3)
        # ms2 peaks
        if ms2_subset is not None:
            ms2_mz = spx.utils.collapse(ms2_subset, keep='mz', how=np.sum)

            # raw
            ms2_out = ms2_mz.loc[(ms2_mz['intensity'] > ms2_threshold) & (ms2_mz['mz'] <= mz_exp + 10), :].sort_values(by='mz')

            # centroided
            ms2_centroid = spx.peakpick.auto(ms2_mz, features='mz',
                                             res=0.01, sigma=0.03, truncate=4, threshold=ms2_threshold)
            ms2_centroid = ms2_centroid.loc[ms2_centroid['mz'] <= mz_exp + 10, :].sort_values(by='mz')

            # string
            ms2_out = ';'.join(['%.4f %i' % (mz, i) for mz, i in zip(ms2_out['mz'].values, ms2_out['intensity'].values)])
            ms2_centroid = ';'.join(['%.4f %i' % (mz, i) for mz, i in zip(ms2_centroid['mz'].values, ms2_centroid['intensity'].values)])

            # append
            d['mz'].append(mz_exp)
            d['dt'].append(dt_exp)
            d['ccs'].append(ccs_exp)
            d['intensity'].append(int_exp)
            d['ms2'].append(ms2_out)

            # append
            d_centroid['mz'].append(mz_exp)
            d_centroid['dt'].append(dt_exp)
            d_centroid['ccs'].append(ccs_exp)
            d_centroid['intensity'].append(int_exp)
            d_centroid['ms2'].append(ms2_centroid)

        # save
        df = pd.DataFrame(d)
        df = df.sort_values(by='intensity', ascending=False)
        df.to_csv(join(output_path, '%s.tsv' % splitext(basename(exp_path))[0]), sep='\t', index=False)

        df_centroid = pd.DataFrame(d_centroid)
        df_centroid = df_centroid.sort_values(by='intensity', ascending=False)
        df_centroid.to_csv(join(output_path, '%s_centroid.tsv' % splitext(basename(exp_path))[0]), sep='\t', index=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SpExtractor: target MS2 extraction script.')
    parser.add_argument('-v', '--version', action='version', version=spx.__version__, help='print version and exit')
    parser.add_argument('data', type=str, help='path to input .h5 file containing spectral data (str)')
    parser.add_argument('output', type=str, help='path to output folder (str)')
    parser.add_argument('--beta', type=float, default=0.12087601109118155,
                        help='ccs calibration parameter beta (float, default=0.1208)')
    parser.add_argument('--tfix', type=float, default=1.9817908554141468,
                        help='ccs calibration parameter tfix (float, default=1.9818)')
    parser.add_argument('--ms1-thresh', type=float, default=1E4,
                        help='intensity threshold (float, default=1E4)')
    parser.add_argument('--ms2-thresh', type=float, default=1E3,
                        help='intensity threshold (float, default=1E3)')

    # parse arguments
    args = parser.parse_args()

    # run
    main(args.data, args.output, args.beta, args.tfix, args.ms1_thresh, args.ms2_thresh)
