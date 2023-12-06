import numpy as np
import pandas as pd
from godale import Executor

def slope(x, y):
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    return m

def bootstrap_slope(args):
    # This function takes x and y and calculates the bootstrap on the slope of the linear regression between both,
    # whereas values are sorted
    
    # unpack args and transform data and dates into numpy arrays
    y, x, nr_bootstraps, point_id = args
    if x:
        x, y = np.array(x), np.array(y)

        boot_means = []
        for _ in range(nr_bootstraps):

            # the fraction of sample we want to include (randon)
            #size = np.abs(np.random.normal(0.5, 0.1))
            size = .66
            
            # select the random samples
            rand_idx = sorted(np.random.choice(np.arange(y.size), int(y.size * size), replace=False))

            # calculate the slope on the randomly selected samples
            s = slope(x[rand_idx], y[rand_idx])

            # add to list of bootstrap samples
            boot_means.append(s)

        # calculate stats adn return
        boot_means_np = np.array(boot_means)
        return np.mean(boot_means_np), np.std(boot_means_np), np.max(boot_means_np), np.min(boot_means_np), point_id
    else:
        return 0, 0, 0, 0, point_id


def run_bs_slope(df, config_dict):
    """
    Parallel implementation of the bootstrap slope function
    """
    
    bs_slope_params = config_dict['bs_slope_params']
    ts_band = config_dict['ts_params']['ts_band']
    point_id_name = config_dict['ts_params']['point_id']
    nr_of_bootstraps = bs_slope_params['nr_of_bootstraps']
    
    args_list, d = [], {}
    for i, row in df.iterrows():
        dates_float = [(date.year + np.round(date.dayofyear/365, 3)) for date in row.dates_mon] 
        args_list.append([row.ts_mon[ts_band], dates_float, nr_of_bootstraps, row[point_id_name]])
        
    executor = Executor(executor="concurrent_threads", max_workers=16)
    for i, task in enumerate(executor.as_completed(
        func=bootstrap_slope,
        iterable=args_list
    )):
        try:
            d[i] = list(task.result())
        except ValueError:
            print("bootstrap task failed")
            
    slope_df = pd.DataFrame.from_dict(d, orient='index')
    slope_df.columns = ['bs_slope_mean', 'bs_slope_sd', 'bs_slope_max', 'bs_slope_min', point_id_name]
    return pd.merge(df, slope_df, on=point_id_name)    