from pathlib import Path
import ee
import geemap
import time
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point
import numpy as np
from matplotlib import pyplot as plt


from dggrid4py import DGGRIDv7

dggrid_instance = DGGRIDv7(
    executable='helpers/dggrid/src/apps/dggrid/dggrid', 
    working_dir='/tmp/', 
    capture_logs=False, 
    silent=True
)


def random_point(geometry):
    
    bounds = geometry.bounds
    while True:
    
        x = (bounds[2] - bounds[0]) * np.random.random_sample(1) + bounds[0]
        y = (bounds[3] - bounds[1]) * np.random.random_sample(1) + bounds[1]
        if Point(x, y).within(geometry):
            break
            
    return Point(x, y)
    
    
def squared_grid(aoi, spacing, crs='ESRI:54017', sampling_strategy='systematic'):

    if isinstance(aoi, ee.FeatureCollection):
        aoi = geemap.ee_to_geopandas(aoi).set_crs('epsg:4326', inplace=True)
    
    # reproject
    if not aoi.crs:
        crs_original = input('Your AOI does not have a coordinate reference system (CRS). Please provide the CRS of the AOI (e.g. epsg:4326): ')
        aoi.set_crs(crs_original, inplace=True)
        
    aoi = aoi.dissolve().to_crs(crs)
    aoi_geom = aoi.iloc[0]['geometry']
    
    # get bounds
    bounds = aoi.bounds
    
    # get orgiin point
    originx = bounds.minx.values[0]
    originy = bounds.miny.values[0]

    # get widht and height of aoi bounds
    width = bounds.maxx - bounds.minx 
    height = bounds.maxy - bounds.miny

    # calculate how many cols and row are those
    columns = int(np.floor(float(width) / spacing))
    rows = int(np.floor(float(height) / spacing))
    
    # create grid cells
    print("Creating grid cells")
    i, l = 1, []
    for column in range(0, columns + 1):
        x = originx + (column * spacing)
        for row in range(0, rows + 1):
            y = originy + (row * spacing)
            cell = box(x, y, x+spacing, y+spacing)
            if cell.intersects(aoi_geom):
                l.append(cell)
                i += 1
    
    # and turn into geodataframe
    print("Turning grid cells into GeoDataFrame...")
    df = pd.DataFrame(l, columns=['geometry'])
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=crs) 
    
    # add points
    print("Creating sampling points...")
    if sampling_strategy == 'systematic':
        # take centroid
        gdf['sample_points'] = gdf.geometry.centroid
        
    elif sampling_strategy == 'random': 
        # create rand points in each grid
        gdf['sample_points'] = gdf.geometry.apply(lambda shp: random_point(shp))
        
    
    # add point id
    print("Adding a unique point ID...")
    gdf['point_id'] = [i for i in range(len(gdf.index))]
    
    # divide to grid and point df
    grid_gdf = gdf.drop(['sample_points'], axis=1)
    gdf['geometry'] = gdf['sample_points']
    point_gdf = gdf.drop(['sample_points'], axis=1)
    
    print('Remove points outside AOI...')
    point_gdf = point_gdf[point_gdf.geometry.within(aoi_geom)]
    
    print(f'Sampling grid consists of {len(point_gdf)} points.')
    return grid_gdf, point_gdf


def hexagonal_grid(aoi, resolution, sampling_strategy='systematic', outcrs='ESRI:54017', projection='ISEA3H'):
    
    # in case we have a EE FC
    if isinstance(aoi, ee.FeatureCollection):
        aoi = geemap.ee_to_geopandas(aoi).set_crs('epsg:4326', inplace=True)
    
    
    if not aoi.crs:
        crs_original = input('Your AOI does not have a coordinate refernce system (CRS). Please provide the CRS of the AOI (e.g. epsg:4326): ')
        aoi.set_crs(crs_original, inplace=True)
            
    # force lat/lon for dggrid
    aoi = aoi.to_crs('EPSG:4326')
    print("Creating hexagonal grid...")
    grid = dggrid_instance.grid_cell_polygons_for_extent(
        projection, 
        resolution, 
        clip_geom=aoi.dissolve().geometry.values[0]
    )
    
    aoi = aoi.dissolve().to_crs(outcrs)
    aoi_geom = aoi.iloc[0]['geometry']
    gdf = grid.to_crs(outcrs)

    if sampling_strategy == 'systematic':
        # take centroid
        gdf['sample_points'] = gdf.geometry.centroid
        
    elif sampling_strategy == 'random': 
        # create rand points in each grid
        gdf['sample_points'] = gdf.geometry.apply(lambda shp: random_point(shp))
        
        
    # add point id
    print("Adding a unique point ID...")
    gdf['point_id'] = [i for i in range(len(gdf.index))]
    
    # divide to grid and point df
    grid_gdf = gdf.drop(['sample_points'], axis=1)
    gdf['geometry'] = gdf['sample_points']
    point_gdf = gdf.drop(['sample_points'], axis=1)
    
    print('Remove points outside AOI...')
    point_gdf = point_gdf[point_gdf.geometry.within(aoi_geom)]
    
    print(f'Sampling grid consists of {len(point_gdf)} points.')
    return grid_gdf.to_crs(outcrs), point_gdf.to_crs(outcrs)


def split_dataframe(df, chunk_size = 25000): 
        chunks = list()
        num_chunks = len(df) // chunk_size + 1
        for i in range(num_chunks):
            chunks.append(df[i*chunk_size:(i+1)*chunk_size])
        return chunks
    

def upload_to_ee(gdf, asset_name):
    
    # get users asset root
    asset_root = ee.data.getAssetRoots()[0]['id']
    
    # if it is already a feature collection
    if isinstance(gdf, ee.FeatureCollection):
        exportTask = ee.batch.Export.table.toAsset(
                collection = gdf,
                description = f'sbae_samples',
                assetId = f'{asset_root}/{asset_name}'
            )

        exportTask.start()
        return

    if len(gdf) > 25000:
        print('Need to run splitted upload routine as dataframe has more than 25000 rows')

        try:
            # create temporary folder
            ee.data.createAsset({'type': 'folder'}, f'{asset_root}/tmp_sbae')
        except:
            pass

        # upload chunks of data to avoi max upload
        chunks = split_dataframe(gdf)
        tasks = []

        for i, chunk in enumerate(chunks):

            point_fc = geemap.geopandas_to_ee(chunk.to_crs("EPSG:4326"))
            exportTask = ee.batch.Export.table.toAsset(
                collection = point_fc,
                description = f'sbae_part_{i}',
                assetId = f'{asset_root}/tmp_sbae/points_{i}'
            )

            exportTask.start()
            tasks.append(exportTask)

        # cha on status
        
        finished=False
        while finished == False:
            time.sleep(30)
            for task in tasks:
                state = task.status()['state']
                if state == 'COMPLETED':
                    finished = True
                else:
                    finished = False
                    break

        # merge assets
        print('aggregate to final')
        child_assets = ee.data.listAssets({'parent': f'{asset_root}/tmp_sbae'})['assets']
        for i, ass in enumerate(child_assets):
            if i == 0:
                point_fc = ee.FeatureCollection(ass['id'])
            else:
                point_fc = point_fc.merge(ee.FeatureCollection(ass['id']))

        print('export final')
        # export to final
        exportTask = ee.batch.Export.table.toAsset(
                collection = point_fc,
                description = f'sbae_aggregated_table',
                assetId = f'{asset_root}/{asset_name}'
            )

        exportTask.start()

        finished=False
        while finished == False:
            time.sleep(30)
            state = exportTask.status()['state']

            if state == 'COMPLETED':
                finished = True
            else:
                finished = False

        print('delete temporary assets')
        child_assets = ee.data.listAssets({'parent': f'{asset_root}/tmp_sbae'})['assets']
        for i, ass in enumerate(child_assets):
            ee.data.deleteAsset(ass['id'])  

        ee.data.deleteAsset(f'{asset_root}/tmp_sbae')
        print(f' Upload completed. You can find the samples at {asset_name}')
        
    else:
        
        # turn into FC
        point_fc = geemap.geopandas_to_ee(gdf.to_crs("EPSG:4326"))
        
        print(' Exporting to asset')
        # export to final
        exportTask = ee.batch.Export.table.toAsset(
                collection = point_fc,
                description = f'sbae_aggregated_table',
                assetId = f'{asset_root}/{asset_name}'
            )

        exportTask.start()

        finished=False
        while finished == False:
            time.sleep(30)
            state = exportTask.status()['state']

            if state == 'COMPLETED':
                finished = True
            else:
                finished = False

                
def save_locally(gdf, ceo_csv=True, gpkg=True, outdir=None):
    
    # if it is already a feature collection
    if isinstance(gdf, ee.FeatureCollection):
        gdf = geemap.ee_to_geopandas(gdf)
    
    if not outdir:
        outdir = Path.home().joinpath('module_results/sbae_point_analysis')
    
    if not isinstance(outdir, Path):
        outdir = Path(outdir)
    
    outdir.mkdir(parents=True, exist_ok=True)
    
    print(f' Saving outputs to {outdir}')
    gdf['LON'] = gdf['geometry'].x
    gdf['LAT'] = gdf['geometry'].y
    
    # sort columns for CEO output
    gdf['PLOTID'] = gdf['point_id']
    cols = gdf.columns.tolist()
    cols = [e for e in cols if e not in ('LON', 'LAT', 'PLOTID')]
    new_cols = ['PLOTID', 'LAT', 'LON'] + cols
    gdf = gdf[new_cols]
    
    if ceo_csv:
        gdf[['PLOTID', 'LAT', 'LON']].to_csv(outdir.joinpath('01_sbae_points.csv'), index=False)
        
    if gpkg:
        gdf.to_file(outdir.joinpath('01_sbae_points.gpkg'), driver='GPKG')
          

def plot_samples(aoi, sample_points, grid_cells=None):
    
    fig, ax = plt.subplots(1, 1, figsize=(25, 25))
    if isinstance(aoi, ee.FeatureCollection):
        geemap.ee_to_geopandas(aoi).to_crs(sample_points.crs).plot(ax=ax, alpha=0.25)
    else:
        aoi.to_crs(sample_points.crs).plot(ax=ax, alpha=0.25)  

    if grid_cells is not None:
        grid_cells.plot(ax=ax, facecolor="none", edgecolor='black', lw=0.1)
    
    sample_points.plot(ax=ax, facecolor='red', markersize=.5)