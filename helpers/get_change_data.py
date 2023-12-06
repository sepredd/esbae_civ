import ee
import json
import time
import pandas as pd
import geopandas as gpd
from pathlib import Path
from godale import Executor
from datetime import timedelta

from helpers.ee.get_time_series import get_time_series
from helpers.ee.util import processing_grid
from helpers.ee.landsat.landsat_collection import landsat_collection
from helpers.ee.ccdc import run_ccdc
from helpers.ee.landtrendr import run_landtrendr
from helpers.ee.global_products import sample_global_products_cell

from helpers.ts_analysis.cusum import run_cusum_deforest, cusum_deforest
from helpers.ts_analysis.bfast_wrapper import run_bfast_monitor
from helpers.ts_analysis.bootstrap_slope import run_bs_slope
from helpers.ts_analysis.timescan import run_timescan_metrics
from helpers.ts_analysis.jrc_nrt import run_jrc_nrt
from helpers.ts_analysis.helpers import subset_ts, remove_outliers, smooth_ts


def upload_tmp_asset(asset_root, fc, asset_name, create_folder=True):
    
    # create temporary folder
    try:
        print(' Deleting temporary folder/assets')
        child_assets = ee.data.listAssets({'parent': f'{asset_root}/tmp_sbae'})['assets']
        for i, ass in enumerate(child_assets):
            ee.data.deleteAsset(ass['id']) 

        ee.data.deleteAsset(f'{asset_root}/tmp_sbae')
    except:
        pass

    print(' Creating temporary folder')
    # create tmp folder in case not there
    ee.data.createAsset({'type': 'folder'}, f'{asset_root}/tmp_sbae')

    # export 
    print(' Exporting table of (missing) points as temporary Earth Engine asset.')
    exportTask = ee.batch.Export.table.toAsset(
                    collection = fc,
                    description = asset_name,
                    assetId = f'{asset_root}/tmp_sbae/{asset_name}'
                )
    exportTask.start()

    finished = False
    while finished == False:
        
        # check every 10 seconds
        time.sleep(10)
        state = exportTask.status()['state']

        if state == 'COMPLETED':
            finished = True
        elif state not in ['COMPLETED', 'READY', 'RUNNING']:
            raise RuntimeError(
                ' ERROR: Upload of the temporary point asset to Earth Engine has failed. Please re-run the notebook.\n'
                ' NOTE that already processed data is not lost.'
            ) 
        else:
            finished = False

    print(' Exporting table of (missing) points was successful.')    
    return ee.FeatureCollection(f'{asset_root}/tmp_sbae/{asset_name}')


def upload_missing_points(df, point_id_name, fc, asset_name):
    
    # get users asset root
    asset_root = ee.data.getAssetRoots()[0]['id']
    
    # in case points have been processed
    if df is not None:
        # create a list of point_ids already processed
        processed_points = df[point_id_name].tolist()

        # filter fc by processed points
        iterative_fc = fc.filter(ee.Filter.inList(point_id_name, ee.List(processed_points)).Not())

        # upload ot new fc
        iterative_fc = upload_tmp_asset(asset_root, iterative_fc, asset_name)

        # calculate size
        left_to_process = iterative_fc.size().getInfo()
        print(f' Found already processed files. Will only consider missing points.')
        print(f' Nr of missing plots: {left_to_process}')
        
    # in case no points have been processed yet
    else:
        
        try:
            print(' Trying to delete temporary Earth Engine folder/assets from previous runs.')
            child_assets = ee.data.listAssets({'parent': f'{asset_root}/tmp_sbae'})['assets']
            for i, ass in enumerate(child_assets):
                ee.data.deleteAsset(ass['id']) 
            
            ee.data.deleteAsset(f'{asset_root}/tmp_sbae')
        except:
            pass

        print(' Creating temporary folder')
        # create tmp folder in case not there
        ee.data.createAsset({'type': 'folder'}, f'{asset_root}/tmp_sbae')
        
        iterative_fc = fc
        left_to_process = fc.size().getInfo()
        print(f' Nr of plots to process: {left_to_process}')
        
    return iterative_fc, left_to_process


def aggregate_tmp_files(tmpdir):
    
    # initialize df for later testing
    df = None
    
    # check if data has been already processed, and use those points
    tmp_files = tmpdir.glob('tmp_results_*.pickle')
    for file in tmp_files:

        df = pd.concat([df, pd.read_pickle(file)], ignore_index=True) if df is not None else pd.read_pickle(file)
        file.unlink()

    # check if a tmp df file is there
    tmp_pckl = tmpdir.joinpath('tmp_df.pickle')
    if tmp_pckl.exists():
        
        # in case we have both, tmp-pickle and recent tmp results data
        if df is not None:  
            df = pd.concat([df, pd.read_pickle(tmp_pckl)], ignore_index=True)
        # in case we only have a temp pickle
        else:  
            df = pd.read_pickle(tmp_pckl)
    
    if df is not None:
        df.to_pickle(tmp_pckl)
        
    # remove noresults tmp files
    tmp_files = tmpdir.glob('tmp_noresults*.txt')
    for file in tmp_files:
        file.unlink()

    return df
    

def extract_to_df(sat_coll, cell_fc, config_file):
    
    # create config file
    with open(config_file) as f:
        config_dict = json.load(f)
    
    # get algorithms from config file
    bfast = config_dict['bfast_params']['run']
    cusum = config_dict['cusum_params']['run']
    ccdc = config_dict['ccdc_params']['run']
    landtrendr = config_dict['landtrendr_params']['run']
    ts_metrics = config_dict['ts_metrics_params']['run']
    jrc_nrt = config_dict['jrc_nrt_params']['run']
    bs_slope = config_dict['bs_slope_params']['run']
    glb_prd = config_dict['global_products']['run']
    
    # get parameters from configuration file
    ts_params = config_dict['ts_params']
    bands = ts_params['bands']
    ts_band = ts_params['ts_band']
    max_cc = ts_params['max_cc']
    
    # get the timeseries data
    df = None 
    if bfast or cusum or ts_metrics or bs_slope or ccdc or landtrendr or jrc_nrt:

        # extract time-series
        df = get_time_series(sat_coll.select(bands), cell_fc, config_dict)
        
        # remove outliers and smooth if set
        df = remove_outliers(df, bands, ts_band) if ts_params['outlier_removal'] else df     
        df = smooth_ts(df, bands) if ts_params['smooth_ts'] else df
        
        # run ccdc
        if ccdc:

            # check taht we have all bands
            check_bpb = all(item in bands for item in config_dict['ccdc_params']['breakpointBands'])
            if 'tmaskBands' in config_dict['ccdc_params']:
                check_tmask = all(item in bands for item in config_dict['ccdc_params']['tmaskBands'])
            else:
                check_tmask = True

            if not check_bpb or not check_tmask:
                print(
                    ' Warning: Skipping CCDC as not all breakpoint bands are available in the time-series data'
                )

            df = run_ccdc(df, cell_fc, config_dict)
            
        # run landtrendr
        df = run_landtrendr(df, cell_fc, config_dict) if landtrendr else df
        
        # run bfast
        df = run_bfast_monitor(df, config_dict) if bfast else df
        
        # run jrc package
        df = run_jrc_nrt(df, config_dict) if jrc_nrt else df
        
        ### THINGS WE RUN WITHOUT HISTORIC PERIOD #####
        # we cut ts data to monitoring period only
        df[['dates_mon', 'ts_mon', 'mon_images']] = df.apply(
            lambda row: subset_ts(row, config_dict['ts_params']['start_monitor'], bands), axis=1, result_type='expand'
        )
        
        # run cusum
        df = run_cusum_deforest(df, config_dict) if cusum else df
        
        # run timescan metrics
        df = run_timescan_metrics(df, config_dict) if ts_metrics else df
        
        # run bs_slope
        df = run_bs_slope(df, config_dict) if bs_slope else df
        
    df = sample_global_products_cell(df, cell_fc, config_dict) if glb_prd else df
        
    return df
    
        
def get_change_data(fc, config_dict):
    
    print(' Setting up the processing pipeline. This may take a moment')
    outdir = config_dict['work_dir']
    if outdir is None:
        outdir = Path.home().joinpath('module_results/sbae_point_analysis')
    else:
        outdir = Path(outdir)
    
    # create tmpdir and outdir
    tmpdir = outdir.joinpath('tmp')
    tmpdir.mkdir(parents=True, exist_ok=True)
    
    # create config file
    config_file = outdir.joinpath('config.json')    
    with open(config_file, "w") as f:
        json.dump(config_dict, f)
    
    # get parameters from configuration file
    ts_params = config_dict['ts_params']
    
    sat = ts_params['satellite']
    ts_band = ts_params['ts_band']
    start_hist = ts_params['start_calibration']
    start_mon = ts_params['start_monitor']
    end_mon = ts_params['end_monitor']
    
    # get processing params
    max_points_per_chunk = config_dict['max_points_per_chunk']
    grid_sizes = config_dict['grid_size_levels']
    point_id_name = config_dict['ts_params']['point_id']
    nr_total_points = fc.size().getInfo()
    
    # if we find any file in the temp directory we check
    df = aggregate_tmp_files(tmpdir)   
    
    # we upload, in case points have been processed, otherwise we start with the original feature collection (see routine for details)
    iterative_fc, left_to_process = upload_missing_points(df, point_id_name, fc, 'tmp_initial_fc')

    # here we start to loop over the different grid sizes
    for grid_size in grid_sizes:
        
        if left_to_process > 0:
    
            # create namespace for tmp and outfiles
            param_string = f'{sat}_{ts_band}_{start_hist}_{start_mon}_{end_mon}_{grid_size}'

            # create aoi based on convex_hull of input feature collection
            aoi = ee.FeatureCollection(iterative_fc.geometry().convexHull())

            # create image collection (not being changed)
            lsat = landsat_collection(
                start_hist, 
                end_mon, 
                aoi, 
                **config_dict['lsat_params']
            )
            
            # create a grid
            grid_fc = processing_grid(aoi, grid_size)
            grid = ee.FeatureCollection(grid_fc).aggregate_array('.geo').getInfo() 
            
            print(f' --------------------------------------------------------------------------------------------')
            print(f' Splitting the aoi in chunks for parallel processing (Level {grid_sizes.index(grid_size)+1}).')
            print(f' Parallelizing on chunks of {grid_size}x{grid_size} degrees, totalling in {len(grid)} chunks.')
            print(f' {left_to_process} points left to process.')
            print(f' --------------------------------------------------------------------------------------------')
            
            # create args_list for each grid cell
            args_list = [(*l, ) for l in list(enumerate(grid))]
        
            # parallizing function (for each grid cell)
            def cell_computation(args):
                
                # get start time for timer
                start_time = time.time()
                
                # extract arguments
                idx, cell = args
                
                # create namespace for tmp and outfiles
                tmp_file = tmpdir.joinpath(f'tmp_results_{idx}_{param_string}.pickle')
                tmp_empty_file = tmpdir.joinpath(f'tmp_noresults_{idx}_{param_string}.txt')

                # check if already been calculated
                if tmp_file.exists() or tmp_empty_file.exists():
                    print(f' Chunk {idx+1} at chunksize of {grid_size} degrees already has been extracted. Going on with next chunk.')    
                    return

                # get geometry of grid cell and filter points for that
                cell_fc = iterative_fc.filterBounds(cell)
                nr_of_points = cell_fc.size().getInfo()

                if nr_of_points > 0 and nr_of_points < max_points_per_chunk:

                    print(f' Processing chunk {idx+1}')
                    df = extract_to_df(lsat, cell_fc, config_file)

                    # write to tmp pickle file
                    if df is not None:
                        df.to_pickle(tmp_file)

                    # stop timer and print runtime
                    elapsed = time.time() - start_time
                    print(f' Chunk {idx+1} with {nr_of_points} points done in: {timedelta(seconds=elapsed)}')    

                elif nr_of_points == 0:
                    with open(tmp_empty_file, 'w') as f:
                        f.write('0 points')
                    print(f' Chunk {idx+1} does not contain any points. Going on with next chunk.')    
                
                elif nr_of_points > max_points_per_chunk :
                    with open(tmp_empty_file, 'w') as f:
                         f.write('too many points')  
                    print(f' More than {max_points_per_chunk} points in chunk {idx+1}. Considering respective points at smaller chunk size level.')
           
            # ---------------debug line--------------------------
            #for args in args_list:
            #    cell_computation(args)

            #cell_computation([1, grid[1], config_file])
            # ---------------debug line end--------------------------

            executor = Executor(executor="concurrent_threads", max_workers=config_dict["workers"])
            for i, task in enumerate(executor.as_completed(
                func=cell_computation,
                iterable=args_list
            )):
                try:
                    task.result()
                except:
                    print(" Gridcell task failed. Trying to process the respective points at a lower chunk size.")
                    pass
        
        if any(tmpdir.iterdir()):
            df = aggregate_tmp_files(tmpdir)

        # if we still haven't catched all points
        if df is not None:
            
            if len(df) < nr_total_points:
            
                gr_size_str = str(grid_size).replace('.', '_')
                asset_name = f'tmp_fc_{gr_size_str}'
                iterative_fc, left_to_process = upload_missing_points(df, point_id_name, fc, asset_name)

            else:
                left_to_process = 0
                break

    # remove the monitoring dates and ts values
    if 'dates_mon' in df.columns:
        df = df.drop(['dates_mon', 'ts_mon'], axis=1)

    # try to turn columsn into numerical, where possible
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except:
            pass

    # create namespace for out files
    param_string_final = f'{sat}_{ts_band}_{start_hist}_{start_mon}_{end_mon}'
    out_gpkg = outdir.joinpath(f'results_{param_string_final}.gpkg')
    out_pckl = outdir.joinpath(f'results_{param_string_final}.pickle')

    # write to pickle with all ts and dates
    df.to_pickle(out_pckl)

    # write to geo file
    if 'dates' in df.columns:
        gdf = gpd.GeoDataFrame(
                    df.drop(['dates', 'ts'], axis=1), 
                    crs="EPSG:4326", 
                    geometry=df['geometry']
              )
    else:
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry=df['geometry'])

    ## write to output and return df# write to output and return df
    gdf.to_file(out_gpkg, driver='GPKG')

    print(" Deleting temporary files")
    # regather tmp files
    tmp_files = tmpdir.glob('tmp_*results*.*')
    # remove tmp files
    for file in tmp_files:
        file.unlink()
    
    # remove any temporary dataframe pickle object
    tmp_pckl = tmpdir.joinpath('tmp_df.pickle')
    if tmp_pckl.exists():
        tmp_pckl.unlink()
    
    tmpdir.rmdir()
    
    print(' Deleting temporary EE assets...')
    # get users asset root
    asset_root = ee.data.getAssetRoots()[0]['id']
    child_assets = ee.data.listAssets({'parent': f'{asset_root}/tmp_sbae'})['assets']
    for i, ass in enumerate(child_assets):
        ee.data.deleteAsset(ass['id']) 
    
    ee.data.deleteAsset(f'{asset_root}/tmp_sbae')
    
    print(" Processing has been finished successfully. Check for final_results files in your output directory.")
