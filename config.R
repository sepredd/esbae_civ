####################################################################################################
####################################################################################################
## Set environment variables
## Contact remi.dannunzio@fao.org 
## 2020/02/15
####################################################################################################
####################################################################################################

####################################################################################################

### Read all external files with TEXT as TEXT
options(stringsAsFactors = FALSE)

### Create a function that checks if a package is installed and installs it otherwise
packages <- function(x){
  x <- as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x,repos="http://cran.r-project.org")
    require(x,character.only=TRUE)
  }
}

### Install (if necessary) two missing packages in your local SEPAL environment
packages(Hmisc)
packages(RCurl)
packages(hexbin)
packages(parallel)
#packages(gfcanalysis)

### Load necessary packages
packages(raster)
packages(rgeos)
packages(ggplot2)
packages(rgdal)
packages(gdalUtils)
packages(plyr)
packages(dplyr)
packages(foreign)
packages(reshape2)
packages(survey)
packages(stringr)
packages(tidyr)

## Get List of Countries 
print(gadm_list  <- data.frame(getData('ISO3')))

homedir  <- paste0(normalizePath("~"),"/")
username <- unlist(strsplit(homedir,"/"))[3]

############ CREATE A FUNCTION TO GENERATE REGULAR GRIDS
generate_grid <- function(aoi,size){
  ### Create a set of regular SpatialPoints on the extent of the created polygons  
  sqr <- SpatialPoints(makegrid(aoi,offset=c(0.5,0.5),cellsize = size))
  
  ### Convert points to a square grid
  grid <- points2grid(sqr)
  
  ### Convert the grid to SpatialPolygonDataFrame
  SpP_grd <- as.SpatialPolygons.GridTopology(grid)
  
  sqr_df <- SpatialPolygonsDataFrame(Sr=SpP_grd,
                                     data=data.frame(rep(1,length(SpP_grd))),
                                     match.ID=F)
  ### Assign the right projection
  proj4string(sqr_df) <- proj4string(aoi)
  sqr_df
}

print(paste0("you are : ",username))
print(paste0("you use ",detectCores()," cores for this session"))

