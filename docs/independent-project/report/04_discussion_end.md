# 5. Discussion

## 5.1 What the satellite pipeline delivers

The first contribution of the project is a measurement. For reservoirs that had no data at all, the pipeline now provides a monthly water area since 2019, at 10 m, with a known provenance for every value. The main methodological risk identified in the literature, cloud cover during the rainy season, turned out to be much smaller than expected once cloud masking was done pixel by pixel rather than scene by scene: 98.7 % of reservoir-months were observed directly. This confirms the value of pixel-level quality scores such as Cloud Score+ (Pasquarella et al., 2023), and it relegates radar to a backup role. The radar reconstruction was indeed imprecise (median relative error 55 %), in line with the known sensitivity of C-band backscatter to wind and dry soils, which earlier radar studies of small reservoirs also had to address (Annor et al., 2009). In this setting, its value is to avoid gaps, not to provide precise values.

The sensitivity analyses also support the choice of the MNDWI sharpened to 10 m (Xu, 2006; Du et al., 2016). The results did not depend on the exact threshold, and the gain of 10 m over 20 m was concentrated on water bodies below 5 ha, which are exactly the small ponds that matter for livestock at the end of the dry season. The comparison with the JRC dataset showed that the application's original inventory, produced at 100 m resolution, missed most of the medium-sized water bodies; a monitoring system that ignores them gives a biased picture of the resource, a concern that echoes the inventory gaps reported for Burkina Faso (Boelee et al., 2009; Venot et al., 2012).

## 5.2 What the forecasts can and cannot do

The forecasting results follow closely the predictability framework of Section 2.3. One month ahead, the current state adds real information to the seasonal cycle, and the random forest improves on climatology by about 20 %, a gain that is statistically robust. Two and three months ahead, the information carried by the current state fades and the model converges to climatology; permutation importance shows this directly. This is not a failure of the learning algorithm but a property of the system: the evidence suggests that, with the information available, the state of a reservoir three months ahead is mostly its seasonal normal.

The oracle experiment adds an important and somewhat counter-intuitive result. A common assumption, and the first improvement one would propose, is that seasonal rainfall forecasts would extend the useful horizon. The experiment shows that even perfect knowledge of monthly rainfall over the sub-basin would not reduce the error. This is consistent with Sahelian hydrology: runoff depends on rainfall intensity, soil crusting and land cover more than on rainfall totals (Mahé & Paturel, 2009), and dry-season losses depend on evaporation and withdrawals. It is also consistent with the hydrological analysis, in which rainy-season rainfall explained part of the peak but nothing of the dry-season minimum. The practical consequence is that effort should not go into integrating seasonal rainfall forecasts, but into better measurement (field validation, volume), finer forcings if any (daily intensity, runoff thresholds) and a better representation of withdrawals.

The seasonal pattern of the error is, from a decision-making point of view, the most useful result. The forecast is most accurate, and most clearly better than climatology, from October to March, during the drawdown. That is when farmers decide how much land to put under dry-season crops, when herders plan their movements, and when programmes decide where to intervene before the end of the dry season. Conversely, the forecast is weakest at the onset of the rainy season, when it matters least for scarcity.

## 5.3 Early warning: strong results, one open question

The alert classifier performed well on every metric, and its probabilities were well calibrated, which means that they can be communicated as such to users. Its most convincing result is the detection of entries into crisis: 70 to 80 % of the reservoirs that crossed the critical threshold were flagged in advance, with 83 to 90 % of alerts confirmed. Two qualifications are needed. First, the simple rule "alert if the forecast filling is below 20 %" did almost as well as the dedicated classifier, so the value comes mainly from the regression forecast and the threshold, not from a sophisticated classifier. Second, and more importantly, critical situations are strongly seasonal (89 % of reservoirs in April). A rule based only on the calendar, "alert if the climatology of the target month is below 20 %", might achieve much of the same performance, and it was not evaluated. Until it is, the added value of the alert beyond the seasonal calendar remains partly unproven. This is the most important methodological gap of the study, and it is cheap to close.

## 5.4 Lessons from the audit of the previous model

The audit of the v2 model illustrates the evaluation pitfalls described in the literature. Its published R² of 0.19 was an artefact of a random split on autocorrelated data (Roberts et al., 2017), and the inference bug meant that users had been shown predictions unrelated to the model. Neither problem was visible without deliberately testing for it. The new pipeline was designed to make these errors structurally impossible: temporal splits, features restricted to information available at forecast time, statistics computed on the training period only, preprocessing serialised with the model, and a single feature module shared by the notebook and the API. For an applied project, this is as important a result as the forecasting skill itself: it is what makes the outputs trustworthy.

## 5.5 Limitations

**Measurement.** The pipeline measures area, not storage; volumes are indicative, valid only for reservoirs of 1 to 35 ha, and the area-based filling ratio is not linear with storage in flat basins. Aquatic vegetation, which can hide open water, is not treated. The catchment of each reservoir is approximated by a HydroBASINS sub-basin. Most importantly, there is no ground truth: the measurements are validated by inter-sensor consistency and comparison with JRC, not by gauges or field surveys.

**Data and validation.** The history is short (five rainy seasons for training, about one and a half years for testing), so the test period may not include extreme years, and conclusions on trends are necessarily weak. Reservoirs are not independent, since they share the same weather. Withdrawals and releases are not observed.

**Alerts and users.** The climatological alert baseline was not evaluated (Section 5.3). User needs were not surveyed: the statement that dry-season planners are the most relevant users is an inference from the results, not an observed demand. The text recommendations displayed by the application are still generated by a language model from the legacy v2 outputs, which contradicts the findings of the audit.

**Scope and sustainability.** The study covers a single 50 km area. Google Earth Engine is free for research and non-commercial use but requires a commercial licence otherwise, which matters for any paid service built on the pipeline.

## 5.6 Practical implications

Three implications follow for WaterTracker. First, the product should present itself as a monitoring and short-term anticipation service, not as a long-range prediction tool: "reliable one month ahead, indicative beyond" is the honest promise. Second, it should be organised around the dry season, which is both when the forecast is best and when decisions are made: an end-of-rainy-season assessment in October-November, then a monthly drawdown update with the one-month forecast and alerts until the rains return. Third, the users who can draw the most value from it are those who allocate resources across many sites they cannot visit, such as irrigation and livestock programmes, NGOs working on water and resilience, and water agencies, rather than individual communities, who already see their own reservoir every day. The results also show that the pipeline transfers to reservoirs it has not seen, which makes an extension to neighbouring areas technically realistic at a very low marginal cost, provided that it is revalidated locally.

# 6. Conclusion and Recommendations

## 6.1 Conclusion

This Independent Project set out to determine whether free satellite data could provide reliable monitoring and useful forecasts of the small reservoirs around Ouagadougou, which are central to dry-season livelihoods but are not measured. It first showed that the existing model could not be trusted: its score vanished under an honest evaluation, and its deployed predictions were corrupted by a software bug. It then built a reproducible pipeline that measures the monthly water area of 100 water bodies at 10 m since 2019, with almost no gaps, and characterised their dynamics: a fast response to rainfall, a regular drawdown, and a dry-season minimum that does not depend on how wet the previous rainy season was.

The forecasting results are clear and honestly bounded. One month ahead, a random forest improves significantly on the reservoir's own seasonal normal and on all simple references, with well-calibrated uncertainty and an early warning that detects most entries into crisis. Two and three months ahead, the forecast is no better than the seasonal normal, and perfect rainfall information would not change this. In other words, the system's value lies in measuring the state of every reservoir every month and anticipating the dry-season drawdown one month ahead, not in long-range prediction.

The research questions are thus answered as follows: the dynamics are well described and only partly driven by rainfall amounts (H1 partly supported); optical-radar fusion gives a continuous and robust series (H2 supported); machine learning beats strong baselines at one month only (H3 partly supported); and probabilistic early warning is reliable, subject to a comparison with a calendar-based rule (H4 supported with a caveat). Beyond the numbers, the project shows that an honest evaluation, including negative results, is what turns a satellite prototype into information that decision-makers can use.

## 6.2 Recommendations

**For the product.**
- Refocus WaterTracker on the dry season with two deliverables: an end-of-rainy-season assessment (filling of each reservoir compared with previous years) and a monthly drawdown update with the one-month forecast, its interval and the alert probability.
- Add an "expected drying-up month" output, which answers the question managers actually ask.
- Replace the language-model recommendations built on the legacy v2 outputs with short, rule-based messages derived from the v3 forecast, validated by a hydrologist, and deliver them in the formats users can access (PDF bulletin, SMS, local languages).
- Communicate the promise honestly: reliable one month ahead, indicative beyond.

**For the method.**
- Evaluate a climatological alert rule and report the alert's added value over it.
- Organise a field validation with a partner: staff-gauge readings on a few dams and photographs with observed levels taken by field agents on small reservoirs.
- Improve volume estimates with a light bathymetric survey of a few reservoirs and, for the large dams, SWOT altimetry.
- Do not prioritise seasonal rainfall forecasts; consider instead daily rainfall intensity and an explicit representation of withdrawals.
- Retrain the model every year after the rainy season and extend the climatology with Landsat imagery.

**For deployment and sustainability.**
- Run a pilot with one programme or NGO over the 2026-2027 dry season, starting with the October-November assessment, and measure whether the information changes decisions (sites prioritised, timing of interventions).
- Clarify the Google Earth Engine licensing conditions before any paid offer, and seek funding through development projects that need multi-site monitoring and evaluation.
- Extend to neighbouring areas only after the pilot, with a local revalidation of the inventory and the model.

# References

@references
Annor, F. O., van de Giesen, N., Liebe, J., van de Zaag, P., Tilmant, A., & Odai, S. N. (2009). Delineation of small reservoirs using radar imagery in a semi-arid environment: A case study in the upper east region of Ghana. *Physics and Chemistry of the Earth, Parts A/B/C, 34*(4-5), 309-315. https://doi.org/10.1016/j.pce.2008.08.005
Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B (Methodological), 57*(1), 289-300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
Biancamaria, S., Lettenmaier, D. P., & Pavelsky, T. M. (2016). The SWOT mission and its capabilities for land hydrology. *Surveys in Geophysics, 37*(2), 307-337. https://doi.org/10.1007/s10712-015-9346-y
Boelee, E., Cecchi, P., & Koné, A. (2009). *Health impacts of small reservoirs in Burkina Faso* (IWMI Working Paper 136). International Water Management Institute.
Breiman, L. (2001). Random forests. *Machine Learning, 45*(1), 5-32. https://doi.org/10.1023/A:1010933404324
Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review, 78*(1), 1-3. https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics, 13*(3), 253-263. https://doi.org/10.1080/07350015.1995.10524599
Du, Y., Zhang, Y., Ling, F., Wang, Q., Li, W., & Li, X. (2016). Water bodies' mapping from Sentinel-2 imagery with modified normalized difference water index at 10-m spatial resolution produced by sharpening the SWIR band. *Remote Sensing, 8*(4), 354. https://doi.org/10.3390/rs8040354
Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A., & Michaelsen, J. (2015). The climate hazards infrared precipitation with stations—a new environmental record for monitoring extremes. *Scientific Data, 2*, 150066. https://doi.org/10.1038/sdata.2015.66
Gal, L., Grippa, M., Hiernaux, P., Peugeot, C., Mougin, E., & Kergoat, L. (2016). Changes in lakes water volume and runoff over ungauged Sahelian watersheds. *Journal of Hydrology, 540*, 1176-1188. https://doi.org/10.1016/j.jhydrol.2016.07.035
Gorelick, N., Hancher, M., Dixon, M., Ilyushchenko, S., Thau, D., & Moore, R. (2017). Google Earth Engine: Planetary-scale geospatial analysis for everyone. *Remote Sensing of Environment, 202*, 18-27. https://doi.org/10.1016/j.rse.2017.06.031
Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009). Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling. *Journal of Hydrology, 377*(1-2), 80-91. https://doi.org/10.1016/j.jhydrol.2009.08.003
Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and practice* (3rd ed.). OTexts. https://otexts.com/fpp3/
Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining: Formulation, detection, and avoidance. *ACM Transactions on Knowledge Discovery from Data, 6*(4), Article 15. https://doi.org/10.1145/2382577.2382579
Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. In *Advances in Neural Information Processing Systems 30* (pp. 3146-3154).
Lehner, B., & Grill, G. (2013). Global river hydrography and network routing: Baseline data and new approaches to study the world's large river systems. *Hydrological Processes, 27*(15), 2171-2186. https://doi.org/10.1002/hyp.9740
Liebe, J., van de Giesen, N., & Andreini, M. (2005). Estimation of small reservoir storage capacities in a semi-arid environment: A case study in the Upper East Region of Ghana. *Physics and Chemistry of the Earth, Parts A/B/C, 30*(6-7), 448-454. https://doi.org/10.1016/j.pce.2005.06.011
Mahé, G., & Paturel, J.-E. (2009). 1896-2006 Sahelian annual rainfall variability and runoff increase of Sahelian Rivers. *Comptes Rendus Geoscience, 341*(7), 538-546. https://doi.org/10.1016/j.crte.2009.05.002
McFeeters, S. K. (1996). The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features. *International Journal of Remote Sensing, 17*(7), 1425-1432. https://doi.org/10.1080/01431169608948714
Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In *Proceedings of the Conference on Fairness, Accountability, and Transparency* (pp. 220-229). ACM. https://doi.org/10.1145/3287560.3287596
Muñoz-Sabater, J., Dutra, E., Agustí-Panareda, A., Albergel, C., Arduini, G., Balsamo, G., Boussetta, S., Choulga, M., Harrigan, S., Hersbach, H., Martens, B., Miralles, D. G., Piles, M., Rodríguez-Fernández, N. J., Zsoter, E., Buontempo, C., & Thépaut, J.-N. (2021). ERA5-Land: A state-of-the-art global reanalysis dataset for land applications. *Earth System Science Data, 13*(9), 4349-4383. https://doi.org/10.5194/essd-13-4349-2021
Nash, J. E., & Sutcliffe, J. V. (1970). River flow forecasting through conceptual models part I — A discussion of principles. *Journal of Hydrology, 10*(3), 282-290. https://doi.org/10.1016/0022-1694(70)90255-6
Pasquarella, V. J., Brown, C. F., Czerwinski, W., & Rucklidge, W. J. (2023). Comprehensive quality assessment of optical satellite imagery using weakly supervised video learning. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops* (pp. 2125-2135). https://doi.org/10.1109/CVPRW59228.2023.00206
Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825-2830.
Pekel, J.-F., Cottam, A., Gorelick, N., & Belward, A. S. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature, 540*(7633), 418-422. https://doi.org/10.1038/nature20584
Roberts, D. R., Bahn, V., Ciuti, S., Boyce, M. S., Elith, J., Guillera-Arroita, G., Hauenstein, S., Lahoz-Monfort, J. J., Schröder, B., Thuiller, W., Warton, D. I., Wintle, B. A., Hartig, F., & Dormann, C. F. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography, 40*(8), 913-929. https://doi.org/10.1111/ecog.02881
Rodrigues, L. N., Sano, E. E., Steenhuis, T. S., & Passo, D. P. (2012). Estimation of small reservoir storage capacities with remote sensing in the Brazilian savannah region. *Water Resources Management, 26*(4), 873-882. https://doi.org/10.1007/s11269-011-9941-8
Romano, Y., Patterson, E., & Candès, E. (2019). Conformalized quantile regression. In *Advances in Neural Information Processing Systems 32* (pp. 3543-3553).
Torres, R., Snoeij, P., Geudtner, D., Bibby, D., Davidson, M., Attema, E., Potin, P., Rommen, B., Floury, N., Brown, M., Navas Traver, I., Deghaye, P., Duesmann, B., Rosich, B., Miranda, N., Bruno, C., L'Abbate, M., Croci, R., Pietropaolo, A., ... Rostan, F. (2012). GMES Sentinel-1 mission. *Remote Sensing of Environment, 120*, 9-24. https://doi.org/10.1016/j.rse.2011.05.028
Venot, J.-P., de Fraiture, C., & Nti Acheampong, E. (2012). *Revisiting dominant notions: A review of costs, performance and institutions of small reservoirs in sub-Saharan Africa* (IWMI Research Report 144). International Water Management Institute. https://doi.org/10.5337/2012.202
Xu, H. (2006). Modification of normalised difference water index (NDWI) to enhance open water features in remotely sensed imagery. *International Journal of Remote Sensing, 27*(14), 3025-3033. https://doi.org/10.1080/01431160600589179

# Appendices

## Appendix A. Reproducibility and correspondence with the notebook

All results in this report come from the notebook `backend/notebooks/WaterTracker_pipeline.ipynb` (run of 8 October 2026). The English report figures are re-plotted from the notebook's stored results by `docs/independent-project/scripts/make_figures.py`; figures marked "labels in French" are the notebook's original outputs, regenerated in English when the notebook is run again.

@table Correspondence between the report and the notebook {#tab:map}
Report section | Notebook section
1.1 Problem statement; 1.3 research questions | Introduction cells
3.2-3.6 Study area, data, inventory, extraction | §1-§4
3.4 and 4.1 Audit of v2 | §6
3.7 and 4.3 Hydrological analysis | §5
3.8 and 4.4 Forecasting | §7-§10, §12
3.9 and 4.5-4.6 Uncertainty, alerts, explainability | §11
3.10 and 4.7 Final model and operational forecast | §13
4.8 and 5 Hypotheses, limitations | §14

To reproduce: install the requirements (`pip install -r requirements.txt -r requirements-notebook.txt` in `backend/`), authenticate to Earth Engine (`earthengine authenticate`), set the database URL and Earth Engine project in `backend/.env`, then run the notebook from `backend/notebooks/`. The full 10 m extraction takes about one hour; later runs reuse the cache.

## Appendix B. Complete test scores

@table Test scores of all models (MAE, RMSE, NSE and KGE at each horizon) {#tab:full}
Model | MAE 1/2/3 | RMSE 1/2/3 | NSE 1/2/3 | KGE 1/2/3
Persistence | 0.186 / 0.326 / 0.424 | 0.289 / 0.442 / 0.535 | 0.45 / −0.30 / −0.90 | 0.71 / 0.31 / −0.01
Seasonal naive | 0.133 / 0.133 / 0.133 | 0.220 / 0.220 / 0.220 | 0.68 / 0.68 / 0.68 | 0.83 / 0.83 / 0.83
Climatology | 0.134 / 0.134 / 0.134 | 0.220 / 0.220 / 0.220 | 0.68 / 0.68 / 0.68 | 0.78 / 0.78 / 0.78
Persistent anomaly | 0.133 / 0.165 / 0.170 | 0.228 / 0.260 / 0.260 | 0.66 / 0.55 / 0.55 | 0.83 / 0.78 / 0.77
Ridge | 0.125 / 0.146 / 0.146 | 0.194 / 0.212 / 0.211 | 0.75 / 0.70 / 0.71 | 0.78 / 0.72 / 0.73
Random forest | 0.108 / 0.133 / 0.130 | 0.176 / 0.196 / 0.194 | 0.80 / 0.74 / 0.75 | 0.80 / 0.74 / 0.75
Gradient boosting (HGB) | 0.108 / 0.135 / 0.133 | 0.178 / 0.200 / 0.200 | 0.79 / 0.73 / 0.73 | 0.82 / 0.76 / 0.77

## Appendix C. System architecture and API

[[fig:arch]] shows how the components of the system fit together, and [[tab:api]] lists the main endpoints of the backend.

@figure docs/independent-project/figures/fig_architecture.png | Architecture of the WaterTracker system {#fig:arch}

@table Main API endpoints of the v3 backend {#tab:api}
Endpoint | Purpose
GET /api/reservoirs | Water bodies with origin, validation status and latest filling
GET /api/reservoirs/{id}/history | Monthly series: area, filling, data source, volume, rainfall
GET /api/reservoirs/{id}/forecast | 1-3 month forecast with 80 % interval and probability of a critical level
GET /api/bulletin | Monthly bulletin of all reservoirs ranked by risk (JSON or CSV)
POST /api/admin/monthly-update | Collection of the latest month, forecasts and statuses (API key)
GET /api/health | Status of the database and external services

## Appendix D. Forecasting features

@table The 32 features of the forecasting models, by group {#tab:features}
Group | Features
State | Filling at lags 0, 1, 2, 3 and 12 months; changes over 1 and 3 months
Climatology | Reservoir climatology of the issue and target months; current anomaly; rainfall climatology of the target month
Past forcings | Rainfall of the month and over 3 and 6 months; rainfall anomaly; potential and actual evaporation; 2 m temperature; soil moisture
Calendar | Sine and cosine of the issue and target months
Physical | Log reference area; JRC mean occurrence and seasonality; elevation; slope; log sub-basin and upstream area; catchment-to-water ratio
Quality | Whether the current value comes from a reliable Sentinel-2 observation
