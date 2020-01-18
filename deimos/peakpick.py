import numpy as np
import scipy.ndimage as ndi
import deimos
import pandas as pd


def auto(data, features=['mz', 'drift_time', 'retention_time'],
         res=[0.01, 0.12, 0.05], sigma=[0.03, 0.3, 0.04], truncate=4, threshold=1E3):
    # safely cast to list
    features = deimos.utils.safelist(features)
    res = deimos.utils.safelist(res)
    sigma = deimos.utils.safelist(sigma)

    # check dims
    deimos.utils.check_length([features, res, sigma])

    # grid data
    edges, H = deimos.grid.data2grid(data, features=features, res=res)

    # sigma in terms of n points
    points = [int(s / r) for s, r in zip(sigma, res)]

    # matched filter
    corr = matched_filter(H, [x + 1 if x % 2 == 0 else x for x in points])

    # peak detection
    footprint = [(truncate * x) + 1 if (truncate * x) % 2 == 0 else truncate * x for x in points]
    peaks = non_maximum_suppression(corr, footprint)

    # convert to dataframe
    peaks = deimos.grid.grid2df(edges, peaks, features=features)

    # threshold
    peaks = peaks.loc[peaks['intensity'] > threshold, :]

    # reconcile with original data
    peaks = reconcile(peaks, data, features=features,
                      sigma=sigma, truncate=truncate, threshold=threshold)

    # resolve case of peaks mapping to same point
    return deimos.utils.collapse(peaks, keep=features, how=np.max)


def reconcile(peaks, data, features=['mz', 'drift_time', 'retention_time'],
              sigma=[0.03, 0.3, 0.04], truncate=4, threshold=1E3):
    # safely cast to list
    features = deimos.utils.safelist(features)
    sigma = deimos.utils.safelist(sigma)

    # check dims
    deimos.utils.check_length([features, sigma])

    # build containers
    res = {k: [] for k in features}
    res['intensity'] = []

    # downselect data
    data_ = data.loc[data['intensity'] > threshold, :]

    # iterate peaks
    count = 0
    for idx, row in peaks.iterrows():
        # targeted search
        subset = deimos.targeted.find_feature(data_,
                                              by=features,
                                              loc=row[features].values,
                                              tol=np.array(sigma) * truncate)

        if subset is not None:
            # pull features
            intensity = subset['intensity'].max()
            if intensity > threshold:
                imax = subset['intensity'].idxmax()
                [res[f].append(subset.loc[imax, f]) for f in features]
                res['intensity'].append(intensity)

                # reset count
                count = 0

            # count low intensity feature
            else:
                count += 1

        # count low intensity feature
        else:
            count += 1

        # too many successive low intensity features found
        if count > 100:
            # resolve case of peaks mapping to same point
            break

    # resolve case of peaks mapping to same point
    return deimos.utils.collapse(pd.DataFrame(res), keep=features, how=np.max)


def non_maximum_suppression(ndarray, size):
    # peak pick
    H_max = ndi.maximum_filter(ndarray, size=size, mode='constant', cval=0)
    peaks = np.where(ndarray == H_max, ndarray, 0)

    return peaks


def matched_filter(ndarray, size):
    return np.square(ndi.gaussian_filter(ndarray, size, mode='constant', cval=0))


def guided(data, by=['mz', 'drift_time', 'retention_time'],
           res=[0.01, 0.12, 1], loc=[0, 0, 0], sigma=[0.06, 0.3, 1], truncate=4, threshold=1E3):
    # safely cast to list
    by = deimos.utils.safelist(by)
    res = deimos.utils.safelist(res)
    loc = deimos.utils.safelist(loc)
    sigma = deimos.utils.safelist(sigma)

    # check dims
    deimos.utils.check_length([by, res, loc, sigma])

    # targeted search
    subset = deimos.targeted.find_feature(data,
                                          by=by,
                                          loc=loc,
                                          tol=np.array(sigma) * truncate)

    # if no data found
    if subset is None:
        return subset

    # peakpick on subset
    peaks = auto(subset, features=by,
                 res=res, sigma=sigma, truncate=truncate, threshold=threshold)

    # if no peaks found
    if len(peaks.index) == 0:
        return None

    return peaks