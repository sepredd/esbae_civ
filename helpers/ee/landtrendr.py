import ee
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
from retry import retry

@retry(tries=5, delay=1, backoff=2)
def run_landtrendr(df, points, config_dict):
    
    # get necessary params
    landtrendr_params = config_dict['landtrendr_params']
    point_id_name = config_dict['ts_params']['point_id']
    start_monitor = config_dict['ts_params']['start_monitor'][0:4]
    end_monitor = config_dict['ts_params']['end_monitor'][0:4]
    ts_band = config_dict['ts_params']['ts_band']
    bands = config_dict['ts_params']['bands']
    scale = config_dict['ts_params']['scale']
    
    # structure data to Image Collection
    args_list, d, coll = [], {}, None
    for i, row in df.iterrows():
        
        # get geom 
        geom = ee.Feature(row.geometry.__geo_interface__)
        squared = geom.buffer(scale, 10).bounds()
        
        # get years of ts
        years = np.unique([date.year for date in row.dates if date.year >= int(start_monitor)])
        
        # get mean value for each year
        ts_yearly = []
        for year in years:

            idx = np.array([True if date.year == year else False for date in row.dates])
            ts_yearly.append(np.nanmean(np.array(row.ts[ts_band])[idx]))

        
        ts = ee.List([value for value in ts_yearly])
        dates = ee.List([int(year) for year in years])
        ts = ts.zip(dates)
        
        def zip_to_image(element):

            values = ee.List(element).get(0)
            year = ee.List(element).get(1)

            return (
                ee.Image.constant(values)
                    .rename(ts_band)
                    .clip(squared)
                    .set('system:time_start',  ee.Date.fromYMD(year, 1, 1).millis())
                    .toFloat()
                )
        
        tsee = ee.ImageCollection(ts.map(zip_to_image))
        coll = coll.merge(tsee) if coll else tsee

    # update params dict
    landtrendr_params.update(timeSeries=tsee)
    landtrendr_params.pop('run', None)

    # run lndtrendr
    lt = ee.Algorithms.TemporalSegmentation.LandTrendr(**landtrendr_params).select(["LandTrendr"])

    # extract data
    vertexMask = lt.arraySlice(0, 3, 4); # slice out the 'Is Vertex' row - yes(1)/no(0)
    vertices = lt.arrayMask(vertexMask); # use the 'Is Vertex' row as a mask for all rows

    left = vertices.arraySlice(1, 0, -1);    # slice out the vertices as the start of segments
    right = vertices.arraySlice(1, 1, None); # slice out the vertices as the end of segments
    startYear = left.arraySlice(0, 0, 1);    # get year dimension of LT data from the segment start vertices
    startVal = left.arraySlice(0, 2, 3);     # get spectral index dimension of LT data from the segment start vertices
    endYear = right.arraySlice(0, 0, 1);     # get year dimension of LT data from the segment end vertices 
    endVal = right.arraySlice(0, 2, 3);      # get spectral index dimension of LT data from the segment end vertices

    dur = endYear.subtract(startYear);       # subtract the segment start year from the segment end year to calculate the duration of segments 
    mag = endVal.subtract(startVal);         # substract the segment start index value from the segment end index value to calculate the delta of segments
    rate = mag.divide(dur);                  # calculate the rate of spectral change

    segInfo = (
        ee.Image.cat([startYear.add(1), endYear, startVal, endVal, mag, dur, rate])
            .toArray(0)
            .mask(vertexMask.mask())
    )

    distDir = -1;

    sortByThis = segInfo.arraySlice(0,4,5).toArray(0).multiply(-1); # need to flip the delta here, since arraySort is working by ascending order
    segInfoSorted = segInfo.arraySort(sortByThis); # sort the array by magnitude
    bigDelta = segInfoSorted.arraySlice(1, 0, 1); # get the first segment in the sorted array (greatest magnitude vegetation loss segment)

    bigDeltaImg = ee.Image.cat(bigDelta.arraySlice(0,0,1).arrayProject([1]).arrayFlatten([['yod']]),
    bigDelta.arraySlice(0,1,2).arrayProject([1]).arrayFlatten([['endYr']]),
    bigDelta.arraySlice(0,2,3).arrayProject([1]).arrayFlatten([['startVal']]).multiply(distDir),
    bigDelta.arraySlice(0,3,4).arrayProject([1]).arrayFlatten([['endVal']]).multiply(distDir),
    bigDelta.arraySlice(0,4,5).arrayProject([1]).arrayFlatten([['mag']]).multiply(distDir),
    bigDelta.arraySlice(0,5,6).arrayProject([1]).arrayFlatten([['dur']]),
    bigDelta.arraySlice(0,6,7).arrayProject([1]).arrayFlatten([['rate']]).multiply(distDir));

    distMask =  bigDeltaImg.select(['mag']).lt(1000).And(bigDeltaImg.select(['dur']).lt(5));

    bigFastDist = bigDeltaImg  #.mask(distMask).int16(); // need to set as int16 bit to use connectedPixelCount for minimum mapping unit filter

    def pixel_value_nan(feature):
        pixel_value = ee.List([feature.get(ts_band), -9999]).reduce(ee.Reducer.firstNonNull())
        return feature.set({ts_band: pixel_value})
        
    sampled_points = bigFastDist.select(['mag', 'dur', 'yod', 'rate', 'endYr']).reduceRegions(**{
      'reducer': ee.Reducer.first(),
      'collection': points,
      'scale': scale,
      'tileScale': 4
    }).map(pixel_value_nan)
    
    url = sampled_points.getDownloadUrl('geojson')

    # Handle downloading the actual pixels.
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise r.raise_for_status()
    
    # write the FC to a geodataframe
    gdf = gpd.GeoDataFrame.from_features(r.json()).fillna(0)
    gdf.rename(columns = {
        'mag':'ltr_magnitude', 
        'dur':'ltr_dur',
        'yod':'ltr_yod',
        'rate':'ltr_rate',
        'endYr':'ltr_end_year'
        }, inplace = True)

    return pd.merge(df, gdf[['ltr_magnitude', 'ltr_dur', 'ltr_yod', 'ltr_rate', 'ltr_end_year', point_id_name]], on=point_id_name)
