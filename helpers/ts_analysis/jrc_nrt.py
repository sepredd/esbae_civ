import os 
if "GDAL_DATA" in list(os.environ.keys()):
    del os.environ["GDAL_DATA"]
if "PROJ_LIB" in list(os.environ.keys()):
    del os.environ["PROJ_LIB"]

import datetime
import pandas as pd
import xarray as xr
import numpy as np

from nrt.monitor.ewma import EWMA
from nrt.monitor.ccdc import CCDC
from nrt.monitor.cusum import CuSum
from nrt.monitor.mosum import MoSum


def get_magnitudes(da, config_dict):
    
    # extract point id column name
    ts_params = config_dict['ts_params']
    start_hist = ts_params['start_calibration']
    start_mon = ts_params['start_monitor']
    end_mon = ts_params['end_monitor']
    point_id_name = ts_params['point_id']
    
    # get point ids to process and mask in DataArray
    points = da[point_id_name].reduce(np.nanmin, axis=0).values
    mask = np.isfinite(points)
        
    try:
        # slice for calibration and monitoring
        history = da.data.sel(time=slice(start_hist, start_mon))
        monitoring = da.data.sel(time=slice(start_mon, end_mon))

        # Instantiate monitoring class and fit stable history
        EwmaMonitor = EWMA(trend=False)
        EwmaMonitor.fit(dataarray=history, method='OLS', screen_outliers='Shewhart')

        #CcdcMonitor = CCDC(trend=True)
        #CcdcMonitor.fit(dataarray=history, screen_outliers='Shewhart')

        CuSumMonitor = CuSum(trend=False)
        CuSumMonitor.fit(dataarray=history, trend=False, method='ROC',  screen_outliers='Shewhart')

        MoSumMonitor = MoSum(trend=False)
        MoSumMonitor.fit(dataarray=history, screen_outliers='Shewhart')

        # Monitor new observations
        for array, date in zip(
            monitoring.values,
            monitoring.time.values.astype('M8[s]').astype(datetime.datetime)
        ):

            EwmaMonitor.monitor(array=array, date=date)
            #CcdcMonitor.monitor(array=array, date=date)
            CuSumMonitor.monitor(array=array, date=date)
            MoSumMonitor.monitor(array=array, date=date)

        df = pd.DataFrame({
            point_id_name: points[mask],
            'ewma_jrc_date':        EwmaMonitor.detection_date[mask],
            'ewma_jrc_change':      np.where(EwmaMonitor.detection_date[mask] > 0, 1, 0),
            'ewma_jrc_magnitude':   EwmaMonitor.process[mask],
            'mosum_jrc_date':       MoSumMonitor.detection_date[mask],
            'mosum_jrc_change':     np.where(MoSumMonitor.detection_date[mask] > 0, 1, 0),
            'mosum_jrc_magnitude':  MoSumMonitor.process[mask],
            'cusum_jrc_date':       CuSumMonitor.detection_date[mask],
            'cusum_jrc_change':     np.where(CuSumMonitor.detection_date[mask] > 0, 1, 0),
            'cusum_jrc_magnitude':  CuSumMonitor.process[mask]
        })
    
    except:
        df = pd.DataFrame({
            point_id_name: points[mask],
            'ewma_jrc_date':        np.zeros(len(points[mask])),
            'ewma_jrc_change':      np.zeros(len(points[mask])),
            'ewma_jrc_magnitude':   np.zeros(len(points[mask])),
            'mosum_jrc_date':       np.zeros(len(points[mask])),
            'mosum_jrc_change':     np.zeros(len(points[mask])),
            'mosum_jrc_magnitude':  np.zeros(len(points[mask])),
            'cusum_jrc_date':       np.zeros(len(points[mask])),
            'cusum_jrc_change':     np.zeros(len(points[mask])),
            'cusum_jrc_magnitude':  np.zeros(len(points[mask])),
        })
    
    # get magnitude values
    return df


def run_jrc_nrt(df, config_dict):
    
    # extract point id column name
    point_id_name = config_dict['ts_params']['point_id']
    
    # create an empty dataframe
    new_df = pd.DataFrame(columns=['time', 'x', 'y', 'data', point_id_name]).set_index(['time', 'x', 'y'])
    
    # restructure dataframe for ingestion into xarray
    for i, row in df.iterrows():

        # get coords, ts and ids
        x = row.geometry.x
        y = row.geometry.y
        ts = row.ts['ndfi']
        point_ids = [float(row[point_id_name]) for i in range(len(ts))]

        # aggregate to arrays for multiindexing
        arrays = [
            row.dates,
            [x for i in range(len(ts))],
            [y for i in range(len(ts))]        
        ]

        # append to empty dataframe
        new_df = pd.concat([
                new_df, 
                pd.DataFrame({'data':ts, point_id_name: point_ids}, index=arrays).rename_axis(['time', 'x', 'y'])
        ])


    # create data array
    da = xr.Dataset.from_dataframe(new_df)
    da['time'] = da['time'].astype('datetime64[ns]')
    da['x'] = da['x'].astype('float32')
    da['y'] = da['y'].astype('float32')
    da['data'] = da.data.astype('float32')
    
    # get change magnitudes
    change_df = get_magnitudes(da, config_dict)
    
    # merge 
    return pd.merge(df, change_df, how='inner', on=point_id_name)
