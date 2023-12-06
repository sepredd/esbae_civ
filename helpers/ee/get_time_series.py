import time

import ee
import pandas as pd
import geopandas as gpd
import numpy as np
import requests
from retry import retry

@retry(tries=3, delay=1, backoff=2)
def get_time_series(imageCollection, points, config_dict):
    
    bands = config_dict['ts_params']['bands']
    ee_bands = ee.List(config_dict['ts_params']['bands'])
    point_id_name = config_dict['ts_params']['point_id']
    scale = config_dict['ts_params']['scale']
    
    # mask lsat collection for grid cell
    cell = points.geometry().convexHull(100)
    masked_coll = imageCollection.filterBounds(cell)
    reducer = ee.Reducer.first().setOutputs(bands) if len(bands) == 1 else ee.Reducer.first()
    
    # mapping function to extract NDVI time-series from each image
    def mapOverImgColl(image):
        
        geom = image.geometry()
        
        def pixel_value_nan(feature):
            
            pixel_values = ee_bands.map(lambda band: ee.List([feature.get(band), -9999]).reduce(ee.Reducer.firstNonNull()))
            properties = ee.Dictionary.fromLists(ee_bands, pixel_values)
            return feature.set(properties.combine({'imageID': image.id()}))
                
        return image.reduceRegions(
            collection = points.filterBounds(geom),
            reducer = reducer,
            scale = scale            
        ).map(pixel_value_nan)

    # apply mapping ufnciton over landsat collection and get the url of the returned FC
    cell_fc = masked_coll.map(mapOverImgColl).flatten().filter(ee.Filter.neq(bands[0], -9999));
    url = cell_fc.getDownloadUrl('geojson')
    
    # Handle downloading the actual pixels.
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise r.raise_for_status()
    
    # write the FC to a geodataframe
    try:
        point_gdf = gpd.GeoDataFrame.from_features(r.json())
    except: # JSONDecodeError:
        return None
        
    if len(point_gdf) > 0:
        return structure_ts_data(point_gdf, point_id_name, bands)
    else:
        return None
    

def structure_ts_data(df, point_id_name, bands):
    
    df.index = pd.DatetimeIndex(pd.to_datetime(df.imageID.apply(lambda x: x.split('_')[-1]), format='%Y%m%d'))
    
    # loop over point_ids and run cusum
    d = {}
    for i, point in enumerate(df[point_id_name].unique()):
        
        # read only orws of points and sort by date
        sub = df[df[point_id_name] == point].sort_index()
        
        #### LANDSAT ONLY ###########
        sub['pathrow'] = sub.imageID.apply(lambda x: x.split('_')[-2])

        # if more than one path row combination covers the point, we select only the one with the most images
        if len(sub.pathrow.unique()) > 1:
            # set an initil length
            length = -1
            # loop through pathrw combinations
            for pathrow in sub.pathrow.unique():
                # check length
                l = len(sub[sub.pathrow == pathrow])
                # compare ot previous length, and if higher reset pathrow and length variable
                if l > length:
                    pr = pathrow
                    length = l
            # finally filter sub df for pathrow with most images
            sub = sub[sub.pathrow == pr]
        #### LANDSAT ONLY ###########
        
        # still duplicates may appear between l9 and l8 that would make bfast crash, so we drop
        sub = sub[~sub.index.duplicated(keep='first')]
        
        # fill ts dictionary
        ts_dict= {}
        for band in bands:
            ts_dict.update({band: sub[band].tolist()})
        
        # write everything to a dict
        d[i] = {
            'point_idx': i,
             point_id_name: point,
            'dates': sub.index,
            'ts': ts_dict, 
            'images': len(sub),
            'geometry': sub.geometry.head(1).values[0]
        }
    
    # turn the dict into a geodataframe and return
    return gpd.GeoDataFrame(pd.DataFrame.from_dict(d, orient='index')).set_geometry('geometry')