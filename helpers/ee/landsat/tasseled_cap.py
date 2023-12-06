import ee


def apply_tc(image):
    
    # Create an Array of Tasseled Cap coefficients.
    coefficients = ee.Array([
      [0.3029, 0.2786, 0.4733, 0.5599, 0.508, 0.1872],
      [-0.2941, -0.243, -0.5424, 0.7276, 0.0713, -0.1608],
      [0.1511, 0.1973, 0.3283, 0.3407, -0.7117, -0.4559],
      [-0.8239, 0.0849, 0.4396, -0.058, 0.2013, -0.2773],
      [-0.3294, 0.0557, 0.1056, 0.1855, -0.4349, 0.8085],
      [0.1079, -0.9023, 0.4119, 0.0575, -0.0259, 0.0252],
    ]);

    # Make an Array Image, with a 1-D Array per pixel.
    opticalBands = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
    arrayImage = image.select(opticalBands).divide(10000).toArray().toArray(1)
    
    # apply TC coefficients
    componentsImage = (
        ee.Image(coefficients)
            .matrixMultiply(arrayImage)
            # Get rid of the extra dimensions.
            .arrayProject([0])
            .arrayFlatten(
                [['brightness', 'greenness', 'wetness', 'fourth', 'fifth', 'sixth']]
            )
    ).multiply(10000).int16()

    return image.addBands(componentsImage)
    
    

