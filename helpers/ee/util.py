import ee
import math

UPPER_LEFT = 0
LOWER_LEFT = 1
LOWER_RIGHT = 2
UPPER_RIGHT = 3
PI = lambda: ee.Number(math.pi)
MAX_SATELLITE_ZENITH = 7.5

def line_from_coords(coordinates, fromIndex, toIndex):
    return ee.Geometry.LineString(ee.List([
        coordinates.get(fromIndex),
        coordinates.get(toIndex)]))


def line(start, end):
    return ee.Geometry.LineString(ee.List([start, end]))


def degToRad(deg):
    return deg.multiply(PI().divide(180))


def value(list, index):
    return ee.Number(list.get(index))


def radToDeg(rad):
    return rad.multiply(180).divide(PI())


def where(condition, trueValue, falseValue):
    trueMasked = trueValue.mask(condition)
    falseMasked = falseValue.mask(invertMask(condition))
    return trueMasked.unmask(falseMasked)


def invertMask(mask):
    return mask.multiply(-1).add(1)


def x(point):
    return ee.Number(ee.List(point).get(0))


def y(point):
    return ee.Number(ee.List(point).get(1))


def determine_footprint(image):
    footprint = ee.Geometry(image.get('system:footprint'))
    bounds = ee.List(footprint.bounds().coordinates().get(0))
    coords = footprint.coordinates()

    xs = coords.map(lambda item: x(item))
    ys = coords.map(lambda item: y(item))

    def findCorner(targetValue, values):
        diff = values.map(lambda value: ee.Number(value).subtract(targetValue).abs())
        minValue = diff.reduce(ee.Reducer.min())
        idx = diff.indexOf(minValue)
        return coords.get(idx)

    lowerLeft = findCorner(x(bounds.get(0)), xs)
    lowerRight = findCorner(y(bounds.get(1)), ys)
    upperRight = findCorner(x(bounds.get(2)), xs)
    upperLeft = findCorner(y(bounds.get(3)), ys)

    return ee.List([upperLeft, lowerLeft, lowerRight, upperRight, upperLeft])


def replace_bands(image, bands):
    result = image
    for band in bands:
        result = result.addBands(band, overwrite=True)
    return result


def processing_grid(aoi, grid_size):
    
    boundbox = aoi.geometry().bounds().buffer(distance=1, proj=ee.Projection('EPSG:4326'))
    
    # return the list of coordinates
    listCoords = ee.Array.cat(boundbox.coordinates(), 1); 

    # get the X and Y -coordinates
    xCoords = listCoords.slice(1, 0, 1);
    yCoords = listCoords.slice(1, 1, 2);

    # reduce the arrays to find the max (or min) value
    xmin = xCoords.reduce('min', [0]).get([0,0])
    xmax = xCoords.reduce('max', [0]).get([0,0])
    ymin = yCoords.reduce('min', [0]).get([0,0])
    ymax = yCoords.reduce('max', [0]).get([0,0])

    xx = ee.List.sequence(xmin, ee.Number(xmax).subtract(ee.Number(grid_size).multiply(0.9)), grid_size)
    yy = ee.List.sequence(ymin, ee.Number(ymax).subtract(ee.Number(grid_size).multiply(0.9)), grid_size)


    def mapOverX(x):
        def mapOverY(y):
            x1 = ee.Number(x)
            x2 = ee.Number(x).add(ee.Number(grid_size))
            y1 = ee.Number(y)
            y2 = ee.Number(y).add(ee.Number(grid_size))

            coords = ee.List([x1, y1, x2, y2]);
            rect = ee.Algorithms.GeometryConstructors.Rectangle(coords, 'EPSG:4326', False);
            return ee.Feature(rect)
        
        return yy.map(mapOverY)
    
    cells = xx.map(mapOverX).flatten()
   
    return ee.FeatureCollection(cells).filterBounds(aoi)


def get_random_point(feature):
    feat = ee.Feature(feature)
    point = ee.Feature(
        ee.FeatureCollection.randomPoints(
            **{"region": feat.geometry(),
               "points": 1,
               "seed": 42,
               "maxError": 100}
        ).first()).set('point_id', feat.id())
    return point.set(
        'LON', point.geometry().coordinates().get(0)).set(
        'LAT', point.geometry().coordinates().get(1)
    )
    

def get_center_point(feature):
    feat = ee.Feature(feature)
    point =  feat.centroid(10).set('point_id', feat.id())
    return point.set(
        'LON', point.geometry().coordinates().get(0)).set(
        'LAT', point.geometry().coordinates().get(1)
    )


def set_id(feature):
    point =  feature.set('point_id', feature.id())
    return point.set(
        'LON', point.geometry().coordinates().get(0)).set(
        'LAT', point.geometry().coordinates().get(1)
    )
