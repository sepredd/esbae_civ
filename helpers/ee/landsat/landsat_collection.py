import ee
from .brdf_correction import apply as apply_brdf
from .tasseled_cap import apply_tc

def add_indices(image):
    
    image4compu = image.select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']).divide(10000)
    
    green = image4compu.select('green')
    red = image4compu.select('red')
    nir = image4compu.select('nir')
    swir1 = image4compu.select('swir1')
    swir2 = image4compu.select('swir2')
    
    ndvi = (nir.subtract(red)).divide((nir.add(red))).multiply(10000).rename('ndvi').int16() 
    ndmi = (nir.subtract(swir1)).divide((nir.add(swir1))).multiply(10000).rename('ndmi').int16() 
    mndwi = (green.subtract(swir1)).divide((green.add(swir1))).multiply(10000).rename('mdnwi').int16() 
    nbr = (nir.subtract(swir2)).divide((nir.add(swir2))).multiply(10000).rename('nbr').int16()
    
    endmembers = {
      "gv": [.0500, .0900, .0400, .6100, .3000, .1000],
      "shade": [0, 0, 0, 0, 0, 0],
      "npv": [.1400, .1700, .2200, .3000, .5500, .3000],
      "soil": [.2000, .3000, .3400, .5800, .6000, .5800],
      "cloud": [.9000, .9600, .8000, .7800, .7200, .6500],
    }
                                           
    unmixed_image = image4compu.unmix(**{
          "endmembers": [endmembers['gv'], endmembers['shade'], endmembers['npv'], endmembers['soil'], endmembers['cloud']],
          "sumToOne": True,
          "nonNegative": True
    }).rename(['GV', 'Shade', 'NPV','Soil','Cloud'])                                       
    
    # Calculate NDFI and add it to the map
    ndfi = unmixed_image.expression(
      '((GV / (1 - SHADE)) - (NPV + SOIL)) / ((GV / (1 - SHADE)) + NPV + SOIL)', 
      {'GV': unmixed_image.select('GV'),
      'SHADE': unmixed_image.select('Shade'),
      'NPV': unmixed_image.select('NPV'),
      'SOIL': unmixed_image.select('Soil')}
    ).multiply(10000).rename('ndfi').int16() 
        
    return (image.addBands(ndvi).addBands(ndmi).addBands(mndwi).addBands(nbr).addBands(ndfi)
        .copyProperties(image)
        .set('system:time_start', image.get('system:time_start'))
        .set('system:footprint', image.get('system:footprint'))
    )


def bitwiseExtract(value, fromBit, toBit=None):
    if not toBit:
        toBit = fromBit
    maskSize = ee.Number(1).add(toBit).subtract(fromBit)
    mask = ee.Number(1).leftShift(maskSize).subtract(1)
    return value.rightShift(fromBit).bitwiseAnd(mask)


def cloudMaskLsatSR(image):
    qa = image.select('QA_PIXEL')
    cloudShadow = bitwiseExtract(qa, 4)
    snow = bitwiseExtract(qa, 5)
    cloud = bitwiseExtract(qa, 6).Not()
    water = bitwiseExtract(qa, 7)
    return image.updateMask(
        cloudShadow.Not()
            .And(snow.Not())
            .And(cloud.Not())
            #.And(water.Not())
    )


def create_collection(collection, start, end, aoi, max_cc):
    
    coll = (
        collection
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt('CLOUD_COVER', max_cc))
    )

    return coll.map(cloudMaskLsatSR)


def apply_scale_factors(image):
    opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2);
    thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0);
    return image.addBands(opticalBands, None, True).addBands(thermalBands, None, True);


def landsat_collection(start, end, aoi, l9=True, l8=True, l7=True, l5=True, l4=True, brdf=True, bands="ndvi", max_cc=75):

    coll = None
    
    if l9:
        # create collection (with masking) and add NDVI
        coll = create_collection(
            ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"), start, end, aoi, max_cc
        ).map(apply_scale_factors).select(
        ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
      )
        
    if l8:
        # create collection (with masking) and add NDVI
        l8_coll = create_collection(
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"), start, end, aoi, max_cc
        ).map(apply_scale_factors).select(
        ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
      )
        
        coll = coll.merge(l8_coll) if coll else l8_coll

    if l7:
        # create collection (with masking) and add NDVI
        l7_coll = create_collection(
            ee.ImageCollection(f"LANDSAT/LE07/C02/T1_L2").filterDate('1970-01-01', '2021-10-30'), start, end, aoi, max_cc
            ).map(apply_scale_factors).select(
                ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
                ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
            )

        # merge collection
        coll = coll.merge(l7_coll) if coll else l7_coll

    if l5:
        # create collection (with masking) and add NDVI
        l5_coll = create_collection(
            ee.ImageCollection(f"LANDSAT/LT05/C02/T1_L2"), start, end, aoi, max_cc
            ).map(apply_scale_factors).select(
                ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
                ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
            )

        # merge collection
        coll = coll.merge(l5_coll) if coll else l5_coll

    if l4:
        # create collection (with masking) and add NDVI
        l4_coll = create_collection(
            ee.ImageCollection(
                f"LANDSAT/LT04/C02/T1_L2"), start, end, aoi, max_cc
            ).map(apply_scale_factors).select(
                ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
                ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
            )

        # merge collection
        coll = coll.merge(l4_coll) if coll else l4_coll

    if brdf:
        coll.map(apply_brdf)

    # scale to int16
    coll = coll.map(
        lambda image: image.multiply(10000).int16()
                    .copyProperties(image)
                    .set('system:time_start', image.get('system:time_start'))
                    .set('system:footprint', image.get('system:footprint'))
    )
                    
    # add indices and tasseled cap
    coll = coll.map(apply_tc).map(add_indices)
    
    # return with selected bands
    return coll.select(bands)