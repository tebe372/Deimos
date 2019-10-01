import spextractor as spx
from os.path import *
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import argparse


plt.switch_backend('agg')


def main(exp_path, output_path, targets_path, mode,
         beta, tfix, mz_res, dt_res, dt_tol, threshold):
    # output directory
    if not exists(output_path):
        os.makedirs(output_path)

    # adducts
    if mode == 'pos':
        adducts = {'+H': 1.00784,
                   '+Na': 22.989769}
    elif mode == 'neg':
        adducts = {'-H': -1.00784}

    # load data
    df = spx.utils.load_hdf(exp_path)

    # load features
    targets = pd.read_excel(targets_path, sheet_name='measuredLibrary')

    # calibrate
    c = spx.calibrate.ArrivalTimeCalibration()
    c.calibrate(tfix=tfix, beta=beta)

    # split by ms level
    data = {}
    data['ms1'] = df.loc[df['ms_level'] == 1, :].drop('ms_level', axis=1).reset_index(drop=True)
    data['ms2'] = df.loc[df['ms_level'] == 2, :].drop('ms_level', axis=1).reset_index(drop=True)

    # find features
    d = {'ikey': [], 'adduct': [], 'mz_lib': [], 'mz_exp': [], 'dt_exp': [], 'ccs_exp': [], 'intensity': [], 'ms2': []}
    for idx, row in targets.iterrows():
        for adduct, adduct_mass in adducts.items():
            # feature
            mz_i = row['Exact Mass'] + adduct_mass

            # ms1 guided peakpicking
            ms1_subset = spx.targeted.find_feature(ms1, by='mz', loc=mz_i, tol=mz_tol)
            ms1_peaks = spx.peakpick.auto(ms1_subset, features=['mz', 'drift_time'],
                                          res=[0.01, 0.12], sigma=[0.03, 0.3])

            # iterate through peaks
            if ms1_peaks is not None:
                for idx2, peak in ms1_peaks.iterrows():
                    mz_exp = peak['mz']
                    dt_exp = peak['drift_time']
                    int_exp = peak['intensity']
                    ccs_exp = c.arrival2ccs(mz_exp, dt_exp)

                    # extract ms2
                    # extract ms2
                    ms2 = spx.targeted.find_feature(data['ms2'], by='drift_time',
                                                    loc=dt_exp,
                                                    tol=4 * 0.3)

                    if ms2 is not None:
                        ms2_mz = spx.utils.collapse(ms2, by='mz', how=np.sum)

                        # sort
                        ms2_out = ms2_mz.loc[(ms2_mz['intensity'] > threshold) & (ms2_mz['mz'] <= mz_i + 10), :].sort_values(by='mz')
                        ms2_out = ''.join(['%.4f %i;' % (mz, i) for mz, i in zip(ms2_out['mz'].values, ms2_out['intensity'].values)])

                        # append
                        d['ikey'].append(row['ikey'])
                        d['adduct'].append(adduct)
                        d['mz_lib'].append(mz_i)
                        d['mz_exp'].append(mz_exp)
                        d['dt_exp'].append(dt_exp)
                        d['ccs_exp'].append(ccs_exp)
                        d['intensity'].append(int_exp)
                        d['ms2'].append(ms2_out)

    df = pd.DataFrame(d)
    df = df.sort_values(by='intensity', ascending=False)
    df.to_csv(join(output_path, '%s.tsv' % splitext(basename(exp_path))[0]), sep='\t', index=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SpExtractor: target MS2 extraction script.')
    parser.add_argument('-v', '--version', action='version', version=spx.__version__, help='print version and exit')
    parser.add_argument('data', type=str, help='path to input .h5 file containing spectral data (str)')
    parser.add_argument('output', type=str, help='path to output folder (str)')
    parser.add_argument('targets', type=str, help='path to input .xlsx spreadsheet containing targets (str)')
    parser.add_argument('--mode', choices=['pos', 'neg'], help='experiment acquisition mode')
    parser.add_argument('--beta', type=float, default=0.12087601109118155,
                        help='ccs calibration parameter beta (float, default=0.1208)')
    parser.add_argument('--tfix', type=float, default=1.9817908554141468,
                        help='ccs calibration parameter tfix (float, default=1.9818)')
    parser.add_argument('--threshold', type=int, default=1000,
                        help='intensity threshold (int, default=1000)')

    # parse arguments
    args = parser.parse_args()

    # run
    main(args.data, args.output, args.targets, args.mode, args.beta, args.tfix, args.threshold)
