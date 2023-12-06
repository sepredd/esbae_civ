import numpy as np
from scipy import stats
from datetime import datetime as dt
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def subset_ts(row, start_monitor, bands):
    """ Helper function to extract only monitoring period
    """
    
    # create index for monitoring period
    idx = row.dates > dt.strptime(start_monitor, '%Y-%m-%d')
    
    # subset dates
    dates = row.dates[idx]
    
    # subset ts data
    ts = {}
    for band in bands:
        ts[band] = np.array(row.ts[band])[idx].tolist()
    
    # get new image length
    images = len(dates)
    
    return dates, ts, images


def rolling_mean(dates, ts, bands, interval='60d'):
    
    d = {}
    for band in bands:
        tmp_df = pd.DataFrame(data=ts[band], index=pd.DatetimeIndex(dates), columns=['ts'])
        d[band] = tmp_df.rolling(interval).mean().ts.tolist()
    
    return d


def smooth_ts(df, bands):

    df['ts'] = df.apply(lambda x: rolling_mean(x.dates, x.ts, bands), axis=1)
    return df


def outlier_removal(dates, ts, bands, ts_band):
   
    # get time-series band to remove outliers
    out_ts = np.array(ts[ts_band]).astype(float)
    z_score = np.abs(stats.zscore(out_ts, axis=0))
    out_ts[z_score > 3] = np.nan
    
    # replace in the ts dict
    ts[ts_band] = out_ts
    
    # create dataframe
    tmp_df = pd.DataFrame(data=ts, index=pd.DatetimeIndex(dates), columns=bands)
    
    # drop nans, aplied to all columns
    tmp_df = tmp_df.dropna()
    
    # aggreagte band values to dict to send back to main df
    d = {}
    for band in bands:
        d[band] = tmp_df[band].tolist()
    
    return tmp_df.index, d


def remove_outliers(df, bands, ts_band):
    
    df[['dates', 'ts']] = df.apply(
        lambda x: outlier_removal(x.dates, x.ts, bands, ts_band), axis=1, result_type='expand'
    )
    return df



def plot_timeseries(pickle_file, point_id, point_id_name='point_id'):
    
    df = pd.read_pickle(pickle_file)
    dates = df[df[point_id_name] == point_id].dates.values[0]
    ts = np.array(df[df[point_id_name] == point_id].ts.values[0])

    sns.scatterplot(x=dates, y=ts)
    
    
def plot_stats_per_class(df, class_column, cols_to_plot):
    
    figs, axs = {}, {}
    
    for col in cols_to_plot:
        figs[col] = plt.figure(figsize=(15,5))
        axs[col] = figs[col].add_subplot(111)
        axs[col] = sns.boxplot(x=class_column, y=col, data=df, ax=axs[col])
        
        if col.startswith('bfast_mag'):
            axs[col].set(ylim=(-3000, 3000))
        
        if col.startswith('bfast_mea'):
            axs[col].set(ylim=(-10, 10))
        
        if col == 'dw_class_mode':
            axs[col].set_ylabel('Dynamic World Class (Mode)')
            axs[col].set_yticks(range(9))
            axs[col].set_yticklabels(
                ['Water (0)', 'Trees (1)', 'Grass (2)', 'Flooded Vegetation (3)', 'Crops (4)', 'Shrubs and Scrub (5)', 'Built (6)', 'Bare (7)', 'Snow and Ice (8)']
            )
            
        if col == 'esri_lc20':
            axs[col].set_ylabel('ESRI Land Cover 2020')
            axs[col].set_yticks(range(11))
            axs[col].set_yticklabels(
                ['No data (1)', 'Water (2)', 'Trees (3)', 'Grass (4)', 'Flooded Vegetation (5)', 'Crops (6)', 'Shrubs and Scrub (7)', 
                 'Built (8)', 'Bare (9)', 'Snow and Ice (10)', 'Clouds (11)']
            )
        
        if col == 'esa_lc20':
            axs[col].set_ylabel('ESA World Cover 2020')
            axs[col].set_yticks([10, 20, 30, 40, 50, 60, 70, 80 , 90, 95, 100])
            axs[col].set_yticklabels(
                ['Trees (10)', 'Shrubland (20)', 'Grassland (30)', 'Cropland (40)', 'Built (50)', 'Barren/Sparse veg. (60)', 'Snow and Ice (70)', 'Open Water (80)',
                'Herbaceous wetland (90)', 'Mangroves (95)', 'Moss and lichen (100)']
            )
    
        plt.grid(axis = 'x')
        
    return figs, axs  