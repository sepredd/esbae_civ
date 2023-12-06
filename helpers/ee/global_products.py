from pathlib import Path 

import ee
import requests
import pandas as pd
import geopandas as gpd
from retry import retry

@retry(tries=3, delay=1, backoff=2)
def sample_global_products_cell(df, points, config_dict):
    
    # get config dict for global products
    config = config_dict['global_products']
    start_monitor = config_dict['ts_params']['start_monitor']
    end_monitor = config_dict['ts_params']['end_monitor']
    point_id_name = config_dict['ts_params']['point_id']
    
    cell = ee.FeatureCollection(points.geometry().convexHull())
   
    # create an empty image to which we can add bands as needed
    dataset = ee.Image.constant(1).rename('to_be_removed')
    
    if config['gfc']:
        ## Global Forest Change (Hansen et al., 2013)
        dataset = dataset.addBands(
                    ee.Image('UMD/hansen/global_forest_change_2020_v1_8').select(
                        ['treecover2000','loss','lossyear','gain'],
                        ['gfc_tc00','gfc_loss','gfc_lossyear','gfc_gain']
                    )
                )
       
    if config['esa_lc20']:
        
        ## ESA WorldCover 2020
        dataset = dataset.addBands(ee.Image('ESA/WorldCover/v100/2020').rename('esa_lc20'))
    
    ## Tropical Moist Forest - JRC 2021
    if config['tmf']:
        
        # get main bands from TMF
        tmf_sub = ee.ImageCollection('projects/JRC/TMF/v1_2020/TransitionMap_Subtypes').filterBounds(cell).mosaic().rename('tmf_sub')
        tmf_main = ee.ImageCollection('projects/JRC/TMF/v1_2020/TransitionMap_MainClasses').filterBounds(cell).mosaic().rename('tmf_main')
        tmf_deg = ee.ImageCollection('projects/JRC/TMF/v1_2020/DegradationYear').filterBounds(cell).mosaic().rename('tmf_degyear')
        tmf_def = ee.ImageCollection('projects/JRC/TMF/v1_2020/DeforestationYear').filterBounds(cell).mosaic().rename('tmf_defyear')          
        dataset = dataset.addBands(tmf_sub).addBands(tmf_main).addBands(tmf_deg).addBands(tmf_def)
            
    if config['tmf_years']:
        
        # get time-series period
        start_year = int(start_monitor[0:4])
        end_year = int(end_monitor[0:4])
        
        tmf_years = ee.ImageCollection('projects/JRC/TMF/v1_2020/AnnualChanges').filterBounds(cell).mosaic()
        all_bands = tmf_years.bandNames()
        # create a list of years falling into the monitoring period
        years_of_interest = ee.List.sequence(start_year, end_year, 1)
        # create actual namespace for bandnames
        bands = years_of_interest.map(lambda year: ee.String('Dec').cat(ee.Number(year).format('%.0f')))
        # check if bands (years) exist in dataset
        bands = bands.map(lambda band: ee.Algorithms.If(all_bands.contains(band), band, "rmv")).removeAll(["rmv"])
        # create new namespace
        new_bands = bands.map(lambda band: ee.String(band).replace("Dec", "tmf_",'g'))
        
        # get years of TMF product
        tmf_all_years = ee.ImageCollection('projects/JRC/TMF/v1_2020/AnnualChanges').mosaic().select(bands, new_bands)
        dataset = dataset.addBands(tmf_all_years)
    
    #if config['copernicus_lc']:
    #    
    #    years_of_interest = ee.List.sequence(start_year, end_year, 1)
        
        
    if config['esri_lc']:
        
        esri_lulc2020= ee.ImageCollection("projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m").filterBounds(cell).mosaic()
        dataset = dataset.addBands(esri_lulc2020.rename('esri_lc20'))
               
    if config['lang_tree_height']:
        
        dataset = dataset.addBands(ee.Image('users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1').rename('lang_tree_height'))

    if config['potapov_tree_height']:
        
        potapov = ee.ImageCollection("users/potapovpeter/GEDI_V27").filterBounds(cell).mosaic().rename('potapov_tree_height')
        dataset = dataset.addBands(potapov)
        
    if config['dynamic_world_tree_prob']:
    
        dynamic_coll = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
                .filterBounds(cell)
                .filterDate(start_monitor, end_monitor)
        )
        
        if dynamic_coll.size().getInfo() != 0:
            
            dynamic = (
                dynamic_coll
                    .select('trees')
                    .reduce(ee.Reducer.mean()
                      .combine(ee.Reducer.min(), None, True)
                      .combine(ee.Reducer.max(), None, True)
                      .combine(ee.Reducer.stdDev(), None, True)
                    )
                    .multiply(100)
                    .uint8()
                    .select(
                        ['trees_mean', 'trees_min', 'trees_max', 'trees_stdDev'],
                        ['dw_tree_prob_mean', 'dw_tree_prob__min', 'dw_tree_prob__max', 'dw_tree_prob__stdDev']
                    )
            )
            
            dataset = dataset.addBands(dynamic)
    
    if config['dynamic_world_class_mode']:
        dynamic_coll = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
                .filterBounds(cell)
                .filterDate(start_monitor, end_monitor)
        )
        
        if dynamic_coll.size().getInfo() != 0:
            dynamic = (dynamic_coll
                .select('label')
                .reduce(ee.Reducer.mode())
                .uint8()
                .select(['label_mode'], ['dw_class_mode'])
            )
            dataset = dataset.addBands(dynamic)
        

        
    if config['elevation']:
        glo30 = (
            ee.ImageCollection("projects/sat-io/open-datasets/FABDEM")
                  .filterBounds(cell)
                  .map(lambda image: ee.Terrain.products(image))
                  .mosaic()
                  .select(['b1', 'slope', 'aspect'],['elevation', 'slope', 'aspect'])
        )
        dataset = dataset.addBands(glo30)
    
    name_of_bands = dataset.bandNames().filter(ee.Filter.neq('item', "to_be_removed"))
    dataset = dataset.select(name_of_bands).clip(cell)
    sampled_points = dataset.reduceRegions(**{
        "reducer": ee.Reducer.first(),
        "collection": points,
        "scale": 30,
        "tileScale": 4
    }).select(name_of_bands.add(point_id_name).add('.geo'))
    url = sampled_points.getDownloadUrl('geojson')
    
    # Handle downloading the actual pixels.
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise r.raise_for_status()
    
    # write the FC to a geodataframe
    gdf = gpd.GeoDataFrame.from_features(r.json())
    gdf['LON'] = gdf['geometry'].x
    gdf['LAT'] = gdf['geometry'].y
    
    # sort columns for CEO output
    gdf['PLOTID'] = gdf[point_id_name]
    cols = gdf.columns.tolist()
    cols = [e for e in cols if e not in ('LON', 'LAT', 'PLOTID')]
    new_cols = ['LON', 'LAT', 'PLOTID'] + cols
    gdf = gdf[new_cols]
    
    if df is not None:
        df = pd.merge(
              gdf.drop(['geometry'], axis=1),
              df, 
              on=point_id_name
        )
    else:
        df = gdf
            
    return df