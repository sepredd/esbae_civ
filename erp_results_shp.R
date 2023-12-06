################ PACKAGES AND DIRECTORIES
source(paste0("/home/sepal-user/sbae_point_analysis_CIV/config.R"))

################ LIRE BDD INITIALE
df <- read.csv('/home/sepal-user/sbae_point_analysis_CIV/erp_1km/bdd_erp_2000_2015_supervised_check_IGN_IC_v2_light.csv')
table(df$vis_ign_2,df$str_dal_ney_3s)

################ LIRE BDD INTERPRETEE
shp <- readOGR("/home/sepal-user/sbae_point_analysis_CIV/erp_1km/final/ERP_RCI_VALIDATION_INT_SIMPLE_161222.shp")
ign <- shp@data
names(ign)

ign$sortid <- row(ign)[,1]

################ FUSIONNER LES DEUX BDD
d0 <- merge(ign,df[,c("PLOTID","str_dal_ney_3s")],by.x="PLOTID",by.y="PLOTID",all.x=T)

table(d0$str_dal_ne,d0$str_dal_ney_3s)
dbf <- arrange(d0,sortid)
dbf <- dbf[,!(names(dbf)  %in% "sortid")]
names(dbf)[ncol(dbf)] <- "str_dal_FAO"
head(dbf)
shp@data <- dbf

writeOGR(shp,"/home/sepal-user/sbae_point_analysis_CIV/erp_1km/final/ERP_RCI_4000pts_strFAO.shp","ERP_RCI_4000pts_strFAO","ESRI Shapefile",overwrite_layer = T)
write.dbf(dbf,"/home/sepal-user/sbae_point_analysis_CIV/erp_1km/final/ERP_RCI_4000pts_strFAO.dbf")



phy <- readOGR("/home/sepal-user/sbae_point_analysis_CIV/inputs/points_grid_ERP_phyto.shp")
dbfy <- phy@data
dbfy[is.na(dbf$Zone),"Zone"] <- "Secteur Ombrophile"
table(dbfy$Zone,useNA = "always")
write.dbf(dbfy,"/home/sepal-user/sbae_point_analysis_CIV/inputs/points_grid_ERP_phyto.dbf")


bdd <- read.csv("/home/sepal-user/sbae_point_analysis/sel_erp_results_square/bdd_erp_2000_2015_supervised_check_IGN_IC_v2.csv")

plot(phy[!(dbf$PLOTID %in% bdd$PLOTID),])
names(bdd)
names(dbf)

names(ign)


names_all <- c("PLOTID","LON","LAT","aspect","dw_class_mode","dw_tree_prob__max","dw_tree_prob__min","dw_tree_prob__stdDev","dw_tree_prob_mean",
               "elevation","esa_lc20","esri_lc20",
               "gfc_gain","gfc_loss","gfc_lossyear","gfc_tc00","lang_tree_height","point_id_x",
               "potapov_tree_height",
               "slope",
               "tmf_2000","tmf_2001","tmf_2002","tmf_2003","tmf_2004","tmf_2005","tmf_2006","tmf_2007","tmf_2008","tmf_2009","tmf_2010","tmf_2011","tmf_2012","tmf_2013","tmf_2014","tmf_2015",
               "tmf_defyear","tmf_degyear","tmf_main","tmf_sub","point_idx","dates",
               
               "ts","images","geometry",
               "ccdc_change_date","ccdc_magnitude",
               "ltr_magnitude","ltr_dur","ltr_yod","ltr_rate","ltr_end_year",
               "mon_images",
               "cusum_change_date","cusum_confidence","cusum_magnitude",
               "ts_mean","ts_sd","ts_min","ts_max",
               "bs_slope_mean","bs_slope_sd","bs_slope_max","bs_slope_min",
               "point_id_y",
               "bfast_magnitude","bfast_means","bfast_change_date",
               "gfc_loss_binary","tmf_def_binary","tmf_deg_binary",
               "green_mean","green_sd","red_mean","red_sd","nir_mean","nir_sd","swir1_mean","swir1_sd","swir2_mean","swir2_sd","ndfi_mean","ndfi_sd","kmeans",
               "cnc_class","prob_stable","prob_change",
               
               "INT1_2000","INT1_2010","INT1_2015","INT1_2020","INT1_2021","CHG_20_21","CHG_00_10","CHG_10_15","CHG_15_20","IC","COMMENT.","P.I_name",
               "cnc_ref_0015","cal_val",
               
               "str_dal_ney_3s","str_dal_ney_4s","str_dal_prp_3s","str_koz_ney_3s","str_koz_ney_4s","str_koz_prp_3s",
               
               "vis_sep_1","vis_ign_1","vis_ign_2")

names_lite <- c("PLOTID","LON","LAT","aspect","elevation","slope","images","mon_images",
                #"dates",
                "dw_class_mode","dw_tree_prob__max","dw_tree_prob__min","dw_tree_prob__stdDev","dw_tree_prob_mean",
                "esa_lc20","esri_lc20",
                "gfc_gain","gfc_loss","gfc_lossyear","gfc_tc00","lang_tree_height",
                #"point_id_x",
                "potapov_tree_height",
                
                "tmf_2000","tmf_2001","tmf_2002","tmf_2003","tmf_2004","tmf_2005","tmf_2006","tmf_2007","tmf_2008","tmf_2009","tmf_2010","tmf_2011","tmf_2012","tmf_2013","tmf_2014","tmf_2015",
                "tmf_defyear","tmf_degyear","tmf_main","tmf_sub",
                #"point_idx",
                
                
                #"ts","geometry",
                "ccdc_change_date","ccdc_magnitude",
                "ltr_magnitude","ltr_dur","ltr_yod","ltr_rate","ltr_end_year",
                "cusum_change_date","cusum_confidence","cusum_magnitude",
                "ts_mean","ts_sd","ts_min","ts_max",
                "bs_slope_mean","bs_slope_sd","bs_slope_max","bs_slope_min",
                "point_id_y",
                "bfast_magnitude","bfast_means","bfast_change_date",
                "gfc_loss_binary","tmf_def_binary","tmf_deg_binary",
                "green_mean","green_sd","red_mean","red_sd","nir_mean","nir_sd","swir1_mean","swir1_sd","swir2_mean","swir2_sd","ndfi_mean","ndfi_sd","kmeans",
                "cnc_class","prob_stable","prob_change",
                
                "INT1_2000","INT1_2010","INT1_2015","INT1_2020","INT1_2021","CHG_20_21","CHG_00_10","CHG_10_15","CHG_15_20",
                #"IC","COMMENT.",
                "P.I_name",
                
                #"cnc_ref_0015",
                "cal_val",
                
                "str_dal_ney_3s",
                #"str_dal_ney_4s","str_dal_prp_3s","str_koz_ney_3s","str_koz_ney_4s","str_koz_prp_3s",
                
                "vis_sep_1","vis_ign_1","vis_ign_2")

names_vis <- c("INT1_2000","INT1_2010","INT1_2015","INT1_2020","INT1_2021","CHG_20_21","CHG_00_10","CHG_10_15","CHG_15_20")

dbr <- dbf[,c("PLOTID",names_vis)]

bdl <- bdd[,names_lite]
head(bdl)
names(dbf) %in% names_vis

table(dbf$PLOTID %in% bdl$PLOTID)
rank
for(rank in 1:nrow(dbf)){
  print(rank)
  plotid <- dbr[rank,"PLOTID"]
  bdl[bdl$PLOTID == plotid,names_vis] <- dbr[rank,names_vis]
}

table(bdl$CHG_00_10)

ddd <- merge(bdl,dbfy[,c("PLOTID","Zone")],by.x="PLOTID",by.y="PLOTID",all.x=T)
head(ddd)
table(ddd$P.I_name)
table(ddd$cnc_class)
names(ddd)
write.csv(ddd,'/home/sepal-user/sbae_point_analysis_CIV/erp_1km/bdd_erp_2000_2015_IGN_v3.csv',row.names = F)
