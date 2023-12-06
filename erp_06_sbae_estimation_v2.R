################ PACKAGES AND DIRECTORIES
source(paste0("/home/sepal-user/sbae_point_analysis_CIV/config.R"))

################ LIRE BDD INITIALE
df <- read.csv('/home/sepal-user/sbae_point_analysis_CIV/erp_1km/bdd_erp_2000_2015_supervised_check_IGN_IC_v2_light.csv')

table(df$str_dal_ney_3s,df$vis_ign_1)
hist(df$prob_change)

################ LIRE BDD INTERPRETEE
ign <- read.csv("/home/sepal-user/sbae_point_analysis_CIV/erp_1km/ign_ERP_CIV_692pts_20221026.csv")
names(ign)

################ GENERER UNE VARIABLE DE DEFORESTATION 2000-2015
ign$cnc_0010 <- 0
ign$cnc_1015 <- 0

ign[ign$CHG_00_10 == "Deforestation","cnc_0010"] <- 1
ign[ign$CHG_10_15 == "Deforestation","cnc_1015"] <- 1

ign$cnc <- ign$cnc_1015 #+ ign$cnc_0010

################ FUSIONNER LES DEUX BDD
d0 <- merge(df,ign,by.x="PLOTID",by.y="PLOTID",all.x=T)

################ AFFICHER LA TABLE CROISEE DES RESULTATS DE DEFORESTATION PAR STRATE
table(d0$cnc,d0$str_dal_ney_3s)

################ CALCUL DES SUPERFICIES ET VARIANCE
## Superficie totale zone ERP
stot <- 4641500

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

print(paste0("Superficie Deforestation 2000-2015 :",round(s_def_t)," ha +/- ",round(ci_def_t)," ha"))

taux <- round(s_def_t/stot*100)

out <- data.frame(cbind(c(s_def_s1,s_def_s2,s_def_s3,s_def_t),
                        c(ci_def_s1,ci_def_s2,ci_def_s3,ci_def_t))
)

names(out) <- c("Area (ha)","IC (ha)")

## Resultat final
out

## Export
write.csv(out,"/home/sepal-user/sbae_point_analysis_CIV/erp_1km/superficie_def.csv",row.names = F)
