import numpy as np
import pandas as pd
import tensorflow as tf 
from godale import Executor

def cusum_calculation(residuals):
    
    # do cumsum calculation
    cumsum = tf.math.cumsum(residuals, axis=0)
    s_max = tf.math.reduce_max(cumsum, axis=0)
    s_min = tf.math.reduce_min(cumsum, axis=0)
    s_diff = tf.subtract(s_max, s_min)
   
    # get podition of max value
    argmax = tf.math.argmax(cumsum, axis=0)
                
    return s_diff, argmax


def bootstrap(stack, s_diff, nr_bootstraps):
    
    # intialize iteration variables
    i, comparison_array, change_sum = 0, tf.zeros(s_diff.shape), tf.zeros(s_diff.shape)
    while i < nr_bootstraps:
        
        # shuffle first axis 
        shuffled_index = tf.random.shuffle(range(stack.shape[0]))
        
        # run cumsum on re-shuffled stack
        s_diff_bs, _ = cusum_calculation(tf.gather(stack, shuffled_index, axis=0))
        
        # compare if s_diff_bs is greater and sum up
        comparison_array += tf.cast(tf.greater(s_diff, s_diff_bs), 'float32') 
        
        # sum up random change magnitude s_diff_bs 
        change_sum += s_diff_bs
        
        # set counter
        i+=1
    
    # calculate final confidence and significance
    confidences = tf.math.divide_no_nan(comparison_array, nr_bootstraps)
    signficance = tf.math.subtract(1, tf.math.divide_no_nan(tf.math.divide_no_nan(change_sum, nr_bootstraps), s_diff))
    
    # calculate final confidence level
    change_point_confidence = tf.math.multiply(confidences, signficance)
    
    return change_point_confidence


def cusum_deforest(args):
    """
    Calculates Page's Cumulative Sum Test according to NASA SERVIR Handbook's implementation
    
    Parameters
    ----------
    stack : pandas series
            dates as index and values of the time-series
    nr_bootstraps : int, default=1000
                
    Returns
    -------
        date : float32
            Change Date in fractional year date format
        confidence : float32
            Change confidence based on the bootstrapping procedure
        magnitude : float32
            Change magnitude based on the s_max parameter
    """
    
    # unpack args
    data, dates, point_id, nr_bootstraps = args
    
    if data:
        stack_tf = tf.convert_to_tensor(np.nan_to_num(data), dtype='float32')
        mask = tf.convert_to_tensor(np.isfinite(data).astype('float32'), dtype='float32')

        # calculate mean
        mean_tf = tf.math.divide_no_nan(tf.math.reduce_sum(stack_tf, axis=0), tf.math.reduce_sum(mask, axis=0))

        # calculate residuals (broadcasting here)
        residuals = tf.math.subtract(stack_tf, mean_tf)

        # mask original nans of stack and treat them as zeros
        residuals = tf.where(tf.math.equal(stack_tf, 0), tf.zeros_like(stack_tf), residuals)

        # get original cumsum caluclation and dates
        s_diff, argmax = cusum_calculation(residuals)

        # get dates into change array
        date = np.array(dates)[argmax.numpy()]
        magnitude = s_diff.numpy()

        # get confidence from bootstrap procedure
        confidence = bootstrap(residuals, s_diff, nr_bootstraps).numpy()
    else:
        date, confidence, magnitude = 0, 0, 0
    return date, confidence, magnitude, point_id


def run_cusum_deforest(df, config_dict):
    """
    Parallel implementation of the cusum_deforest function
    """
    
    cusum_params = config_dict['cusum_params']
    ts_band = config_dict['ts_params']['ts_band']
    nr_of_bootstraps = cusum_params['nr_of_bootstraps']
    point_id_name = config_dict['ts_params']['point_id']
    
    args_list, d = [], {}
    for i, row in df.iterrows():
        dates_float = [date.year + np.round(date.dayofyear/365, 3) for date in row.dates_mon]
        args_list.append([row.ts_mon[ts_band], dates_float, row[point_id_name], nr_of_bootstraps])
        
    executor = Executor(executor="concurrent_threads", max_workers=16)
    for i, task in enumerate(executor.as_completed(
        func=cusum_deforest,
        iterable=args_list
    )):
        try:
            d[i] = list(task.result())
        except ValueError:
            print("cusum task failed")
            
    cusum_df = pd.DataFrame.from_dict(d, orient='index')
    cusum_df.columns = ['cusum_change_date', 'cusum_confidence', 'cusum_magnitude', point_id_name]
    return pd.merge(df, cusum_df, on=point_id_name)    