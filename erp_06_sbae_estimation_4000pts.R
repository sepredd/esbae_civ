################ PACKAGES AND DIRECTORIES
source(paste0("/home/sepal-user/sbae_point_analysis_CIV/config.R"))

################ LIRE BDD INITIALE
df  <- read.csv('/home/sepal-user/sbae_point_analysis_CIV/erp_1km/bdd_erp_2000_2015_supervised_check_IGN_IC_v2_light.csv')

################ LIRE BDD INTERPRETEE
shp <- readOGR("/home/sepal-user/sbae_point_analysis_CIV/erp_1km/final/ERP_RCI_4000pts_strFAO_CQ.shp")

################ LIRE FICHIER SUPERFICIE
ar_phy <- read.csv("/home/sepal-user/sbae_point_analysis_CIV/erp_1km/ign_ERP_CIV_4000pts_physio_strata_areas.csv")


################ AFFICHER LA TABLE CROISEE DES RESULTATS DE DEFORESTATION PAR STRATE
table(df$str_dal_ney_3s,df$vis_ign_1)
hist(df$prob_change)


################ CALCUL DES SUPERFICIES ET VARIANCE
## Superficie totale zone ERP
stot <- ar_phy[ar_phy$AOI == "TOTAL","Total.ERP"]


################ GENERER UNE VARIABLE DE DEFORESTATION 
ign <- shp@data
names(ign)

table(ign$INT1_2010,ign$INT1_2015,ign$CHG_10_15)

# class_depart <- 11
# class_arrive <- 50
# annee_depart <- 2010
# annee_arrive <- 2015

sbae <- function(annee_depart,annee_arrive,class_depart,class_arrive){
  ign$cnc <- 0
  ign[ign[,paste0("INT1_",annee_depart)] == class_depart & ign[,paste0("INT1_",annee_arrive)] == class_arrive,"cnc"] <- 1
  
  ################ FUSIONNER LES DEUX BDD
  d0 <- merge(df,ign,by.x="PLOTID",by.y="PLOTID",all.x=T)
  table(d0$cnc,d0$str_dal_ney_3s)
  
  ## Poids des 3 strates
  w_s1 <- nrow(d0[d0$str_dal_ney_3s == 1,]) / nrow(d0)
  w_s2 <- nrow(d0[d0$str_dal_ney_3s == 2,]) / nrow(d0)
  w_s3 <- nrow(d0[d0$str_dal_ney_3s == 3,]) / nrow(d0)
  
  ## Superficies des 3 strates
  s_s1 <- w_s1 * stot
  s_s2 <- w_s2 * stot
  s_s3 <- w_s3 * stot
  
  s_s1 + s_s2 + s_s3 == stot
  
  ## Probabilité des points de deforestation dans chaque strate
  p_def_s1 <- nrow(d0[d0$cnc == 1 & d0$str_dal_ney_3s == 1 & !is.na(d0$cnc),]) / nrow(d0[d0$str_dal_ney_3s == 1 & !is.na(d0$cnc),])
  p_def_s2 <- nrow(d0[d0$cnc == 1 & d0$str_dal_ney_3s == 2 & !is.na(d0$cnc),]) / nrow(d0[d0$str_dal_ney_3s == 2 & !is.na(d0$cnc),])
  p_def_s3 <- nrow(d0[d0$cnc == 1 & d0$str_dal_ney_3s == 3 & !is.na(d0$cnc),]) / nrow(d0[d0$str_dal_ney_3s == 3 & !is.na(d0$cnc),])
  
  ## Superficie de deforestation dans chaque strate
  s_def_s1 <- p_def_s1 * s_s1
  s_def_s2 <- p_def_s2 * s_s2
  s_def_s3 <- p_def_s3 * s_s3
  
  s_def_t  <- s_def_s1 + s_def_s2 + s_def_s3
  
  ## Variance de deforestation dans chaque strate
  v1 <- var(d0[d0$str_dal_ney_3s == 1 & !is.na(d0$cnc),"cnc"])/ nrow(d0[d0$str_dal_ney_3s == 1 & !is.na(d0$cnc),])
  v2 <- var(d0[d0$str_dal_ney_3s == 2 & !is.na(d0$cnc),"cnc"])/ nrow(d0[d0$str_dal_ney_3s == 2 & !is.na(d0$cnc),])
  v3 <- var(d0[d0$str_dal_ney_3s == 3 & !is.na(d0$cnc),"cnc"])/ nrow(d0[d0$str_dal_ney_3s == 3 & !is.na(d0$cnc),])
  
  ## Erreur Standard
  sd_def_s1 <- sqrt(v1) * s_s1
  sd_def_s2 <- sqrt(v2) * s_s2
  sd_def_s3 <- sqrt(v3) * s_s3
  sd_def_t  <- sqrt(sd_def_s1*sd_def_s1 + sd_def_s2*sd_def_s2 + sd_def_s3*sd_def_s3)
  
  ## Intervalles confiance
  ci_def_s1 <- 1.67*sd_def_s1
  ci_def_s2 <- 1.67*sd_def_s2
  ci_def_s3 <- 1.67*sd_def_s3
  ci_def_t  <- 1.67*sd_def_t
  
  print(paste0("Superficie Deforestation ",annee_depart,"-",annee_arrive,", Transition ",class_depart,">",class_arrive," : ",round(s_def_t)," ha +/- ",round(ci_def_t)," ha"))
}


sbae(2020,2021,11,13)



# taux <- round(s_def_t/stot*100)
# 
# out <- data.frame(cbind(c(s_def_s1,s_def_s2,s_def_s3,s_def_t),
#                         c(ci_def_s1,ci_def_s2,ci_def_s3,ci_def_t))
# )
# 
# names(out) <- c("Area (ha)","IC (ha)")
# 
# ## Resultat final
# out
# 
# ## Export
# #write.csv(out,"/home/sepal-user/sbae_point_analysis_CIV/erp_1km/superficie_def.csv",row.names = F)
