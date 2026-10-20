# 2. Theoretical Framework

## 2.1 The water balance of a small reservoir

The state of a reservoir at any time results from a water balance. Writing S for the stored volume, its change over a month is

@eq dS/dt = P·A + Q_in − E·A − W − I − Q_out

where P is the rain falling directly on the water surface A, Q_in the runoff from the catchment, E the open-water evaporation rate, W the withdrawals (irrigation, livestock, domestic use), I the infiltration and Q_out the spill or releases. In the Sahel this balance has two regimes. During the rainy season, Q_in dominates: the reservoir fills within weeks, and the amount of water it receives depends on rainfall intensity, soil crusting and land cover rather than on the rainfall total alone (Mahé & Paturel, 2009). During the dry season, inflows stop and the reservoir follows a drawdown governed by evaporation, which reaches 6 to 8 mm per day, by withdrawals and by infiltration. Because the dry-season terms vary slowly and regularly, the drawdown is expected to be more predictable than the filling.

Satellites observe A, not S. The two are linked by the reservoir's bathymetry, often summarised by a power law V = k·A^b. Liebe et al. (2005) found V = 0.00857 × A^1.4367 (V in m³, A in m²) for small reservoirs of northern Ghana. Since b > 1, volume falls faster than area: a reservoir at half its reference area holds only about 37 % of its corresponding volume. This has two consequences for the project. First, the filling ratio used as the target (area divided by a reference area) is an index of the state of the reservoir, not a direct measure of storage. Second, a critical threshold set at 20 % of the reference area corresponds to roughly 10 % of the volume, i.e. a residual pond.

## 2.2 Physical basis of satellite water detection

Water absorbs almost all incident radiation in the near-infrared and short-wave infrared, while vegetation reflects strongly in the near-infrared and bare soils and built-up surfaces reflect in the SWIR. Normalised difference indices exploit this contrast. The NDWI = (Green − NIR) / (Green + NIR) (McFeeters, 1996) is positive over water; the MNDWI = (Green − SWIR) / (Green + SWIR) (Xu, 2006) separates water from bright soils and settlements better, and handles the turbid, sediment-laden water of Sahelian reservoirs well. A pixel is classified as water when the index exceeds a threshold, conventionally 0.

Two sources of error follow from the sensor's geometry. First, a pixel on the shoreline mixes water and land, so the area of a small water body carries an error proportional to its perimeter: the finer the resolution, the smaller that error. Second, clouds and their shadows hide the surface; a masked pixel is unknown, not dry, so an image with 30 % masked pixels may underestimate the water area by up to 30 %. Radar avoids the second problem. A C-band SAR emits microwaves that cross clouds; calm open water acts as a mirror and sends the signal away from the sensor, so it appears dark (low VV backscatter). The detection threshold, however, depends on wind roughening and on soil moisture: very dry sandy soils can be as dark as water. Radar areas must therefore be calibrated against optical areas where both are available.

## 2.3 Predictability and the value of a forecast

A forecast of a reservoir's state draws on two sources of predictability. The first is the initial state: a store of water changes gradually, so its current level and recent trend carry information about the near future. This information decays with the horizon. The second is the seasonal cycle: every reservoir fills and empties at roughly the same time each year, so the long-term average for the target month (the climatology) is a strong predictor at any horizon. What lies beyond these two sources (an unusually wet August, a sudden increase in withdrawals) is the unpredictable part, unless it can be forecast from external information such as seasonal rainfall forecasts.

This framework determines how a model must be judged. A model is useful only if it beats the best simple reference that already exploits these sources: persistence (the current state), the seasonal naive forecast (last year's value) and climatology (Hyndman & Athanasopoulos, 2021). The skill score, 1 − MAE_model / MAE_reference, measures the improvement over that reference; a positive but non-significant skill means that the model has learnt nothing beyond the reference. It also determines what can be expected: at one month, the initial state should add to climatology; at two or three months, the model should converge to climatology unless future rainfall matters and can be anticipated.

Several models are compared. A ridge regression is a regularised linear model that reveals whether the relationships are essentially linear. A random forest averages many decision trees grown on bootstrap samples with random feature subsets, which makes it robust and little sensitive to tuning (Breiman, 2001). Histogram-based gradient boosting builds trees sequentially, each correcting the errors of the previous ones, and supports quantile losses (Ke et al., 2017). Forecasts at several horizons follow a direct strategy (one model per horizon), which avoids the accumulation of errors of recursive forecasts.

## 2.4 Honest evaluation: leakage, dependence and uncertainty

Machine-learning evaluation assumes that test data are independent of training data. Monthly observations of the same reservoir are strongly autocorrelated, and neighbouring reservoirs share the same weather. A random split therefore places in the training set the months that surround each test month, and the model is rewarded for interpolating rather than forecasting (Roberts et al., 2017). The appropriate design is a temporal split, in which the model is trained on earlier years, tuned on a later year and tested once on the most recent years. Any statistic computed on the whole series and used as a feature, such as a long-term mean that includes future values, is a form of leakage (Kaufman et al., 2012). These principles are the main criteria used to audit the previous model.

A forecast that will support decisions must carry its uncertainty. Quantile regression estimates, for instance, the 10th and 90th percentiles of the target, which form a nominal 80 % interval; in practice such intervals are often too narrow. Conformalized quantile regression (Romano et al., 2019) corrects them using the errors observed on a calibration set, and guarantees a coverage close to the nominal level if future errors resemble the calibration errors (exchangeability).

## 2.5 Early warning as a decision problem

An early-warning system turns a forecast into a decision: alert or no alert. The event of interest is defined here as the filling ratio falling below 20 % of the reference area. A probabilistic classifier estimates the probability of this event; its quality is assessed by its discrimination (ROC-AUC, and PR-AUC when the event is imbalanced), by its calibration (a predicted probability of 0.8 should materialise 80 % of the time) and by the Brier score, the mean squared error of the probabilities (Brier, 1950). Turning probabilities into alerts requires a threshold, which trades missed events against false alarms; maximising the F1 score is a neutral choice when the costs of the two errors are unknown. Finally, an alert is valuable only if it anticipates something a manager does not already know: reservoirs that are already critical are trivially detected by persistence, so the demanding test is the detection of entries into crisis.

## 2.6 Conceptual framework

The project combines these elements in a chain ([[fig:workflow]]): a quality-controlled inventory defines what is measured; physical principles of remote sensing turn images into monthly areas; the water balance and the area-volume relationship give these areas a hydrological meaning; predictability theory and honest evaluation determine what the forecasting models can deliver; and decision theory turns forecasts into alerts. The chain is closed by documentation (a model card, Mitchell et al., 2019) so that users know what the outputs can and cannot support.

# 3. Methodology

## 3.1 Research design

The project follows a quantitative, observational and predictive design. It relies exclusively on secondary data: open satellite and climate archives, and the application's database of water points. It proceeds in five steps: (1) audit of the existing model; (2) construction of the reservoir inventory; (3) extraction and fusion of monthly water areas; (4) exploratory hydrological analysis; (5) forecasting, uncertainty and early warning, evaluated on held-out years. All steps are implemented in a single Jupyter notebook (`backend/notebooks/WaterTracker_pipeline.ipynb`) that reuses the application's configuration and code, so that the model evaluated is exactly the one deployed ([[fig:workflow]]).

@figure docs/independent-project/figures/fig00_workflow.png | Technical workflow of the WaterTracker v3 pipeline {#fig:workflow}

## 3.2 Study area

The study area is a 50 km disc around Ouagadougou (centre 12.3647° N, 1.5221° W), covering about 7,729 km² of the central plateau of Burkina Faso. The climate is Sudano-Sahelian, with a single rainy season from June to October and June-September rainfall of 650-800 mm per year over the study period. The area includes large dams supplying the capital (such as Ziga and Loumbila) and many small and medium reservoirs used for agriculture and livestock ([[fig:study]]).

@figure backend/reports/figures/fig01_study_area.png | Study area: reservoirs of the application (red dots), reservoirs added from JRC (orange triangles), analysis regions (cyan) and HydroBASINS level-10 sub-basins (white), on a Sentinel-2 composite of October 2024. Labels in French from the notebook run. {#fig:study}

## 3.3 Data

The data sources are listed in [[tab:data]].

@table Data sources used in the project {#tab:data}
Dataset | Provider | Resolution | Use
Sentinel-2 surface reflectance (harmonised) | ESA Copernicus, via GEE | 10-20 m, 5-day revisit | Water area (MNDWI), NDWI and NDVI
Cloud Score+ | Google (Pasquarella et al., 2023) | 10 m | Pixel-level cloud and shadow mask
Sentinel-1 GRD, VV, IW mode | ESA Copernicus, via GEE | 10 m pixel | Gap-filling of cloudy months
CHIRPS daily rainfall | Climate Hazards Center (Funk et al., 2015) | 0.05° | Monthly rainfall over each sub-basin
ERA5-Land monthly | ECMWF (Muñoz-Sabater et al., 2021) | 0.1° | Temperature, potential and actual evaporation, soil moisture
JRC Global Surface Water v1.4 | EC JRC (Pekel et al., 2016) | 30 m | Inventory check, permanence features
SRTM | NASA/USGS | 30 m | Elevation and slope
HydroBASINS level 10 | WWF (Lehner & Grill, 2013) | 100-400 km² basins | Catchment of each reservoir
WaterTracker water points | Application database (PostGIS) | 65 points, OSM outlines | Initial inventory
v2 observations | Application database | Half-yearly, 650 rows | Audit of the previous model

## 3.4 Audit of the previous model

Before any new development, the v2 model was re-run on the database to test four suspected problems: (D1) a target, "number of half-years until the NDWI falls below 0.2", almost determined by the season; (D2) an information leak through a feature computed on the whole series and a random train-test split; (D3) a mismatch between training (raw inputs) and inference (scaled inputs) in the API; (D4) the ability of a single-point NDWI to follow the reservoir's water area. Each problem was tested with a number: the accuracy of a rule based only on the season (D1), the model's score under a random and a temporal split, with and without the suspect feature (D2), the gap between correct and served predictions (D3), and correlations between the point NDWI and the new filling ratio, within dry seasons only (D4).

## 3.5 Inventory construction

The 65 water points of the application were checked for geometric validity and duplicates: points sharing exactly the same polygon were merged into one physical reservoir, giving 44 reservoirs. Each reservoir received an analysis region large enough to capture its maximum extent: the polygon plus a 100 m buffer for water bodies of 5 ha or more, and a 300 m disc around the centroid otherwise, all computed in UTM zone 30N. The inventory's completeness was then tested against all JRC water bodies of 10 ha or more with an occurrence of at least 10 %; the 56 missing water bodies were added with their JRC outline, giving 100 analysis regions. Each region was linked to its HydroBASINS level-10 sub-basin (42 distinct sub-basins), over which climate variables are averaged, and characterised by static features (JRC maximum extent, permanence and seasonality, elevation, slope, catchment size).

## 3.6 Water-area extraction and fusion

For every month from January 2019 to August 2026 (92 months), a Sentinel-2 median composite was built after masking pixels with a Cloud Score+ value below 0.60. The 20 m SWIR band was resampled to 10 m (Du et al., 2016) and the MNDWI computed; pixels with MNDWI > 0 were counted as water, and the area summed over each region at 10 m. The same composite also gave the area for MNDWI thresholds of −0.1 and +0.1 (sensitivity analysis), the area from the native-10 m NDWI (control of the sharpening) and the fraction of valid pixels. A month was considered reliable when at least 90 % of the region was observed. In parallel, the monthly median Sentinel-1 VV backscatter gave water areas for thresholds from −14 to −20 dB. All computations ran server-side in Google Earth Engine, with results cached as Parquet files.

The radar threshold was chosen on the reliable months of the training period only, by maximising the median correlation between radar and optical areas per reservoir. A robust linear mapping (Theil-Sen estimator) from radar to optical area was then fitted for each reservoir; it was used only if at least 12 common months and a correlation of 0.6 or more were available. Its accuracy was assessed on reliable months from 2024 onwards, never seen during calibration. The fused series took, in order of priority, the reliable optical value, the recalibrated radar value, or a linear interpolation over gaps of at most two months; isolated spikes in non-optical values were removed with a Hampel filter. Each value keeps its provenance.

The area was then normalised by a reference area A_ref, the 95th percentile of the fused area over the training period only (2019-2023), to obtain a dimensionless filling ratio, capped at 1.5. Reservoirs with A_ref below 2 ha were excluded, leaving 96 modelled reservoirs and 8,832 reservoir-months. An indicative volume was computed with the Liebe et al. (2005) relationship for reservoirs within its domain of validity (1-35 ha).

## 3.7 Hydrological analysis

The regime was described by the distribution of the filling ratio per calendar month. The response to rainfall was measured by the median, across reservoirs, of the cross-correlation between monthly rainfall and the change in filling at lags of zero to three months. The link between rainy-season rainfall (June-September) and the annual peak and the following dry-season minimum was measured with Spearman correlations, using hydrological years starting in July. The dry-season drawdown was summarised by the median monthly change in filling from November to May. Inter-annual trends in the dry-season minimum were tested reservoir by reservoir with the Mann-Kendall test and Theil-Sen slopes, with a Benjamini-Hochberg correction for multiple testing (Benjamini & Hochberg, 1995).

## 3.8 Forecasting design

**Target and horizons.** For each reservoir and each month t, the target is the filling ratio at t + h, for h = 1, 2 and 3 months, with one model per horizon. Two formulations were compared: predicting the level fill(t + h) or the change fill(t + h) − fill(t).

**Features.** Thirty-two features, all known at the end of month t, describe the current state (filling at lags 0 to 3 and 12 months, recent changes), the reservoir's climatology for the issue and target months and the current anomaly, past forcings (rainfall over 1, 3 and 6 months and its anomaly, potential and actual evaporation, temperature, soil moisture), the calendar (sine and cosine of the issue and target months), static characteristics (reference area, JRC permanence and seasonality, elevation, slope, catchment size) and a data-quality flag. For training rows, the target-month climatology was computed excluding the target's year. The feature code is shared with the API (`ml/features.py`), so that inference uses exactly the same computation. A control checks that no feature is almost identical to the target (|r| > 0.95).

**Validation protocol.** Data were split by target month: training (2019-2023), validation (2024) and test (2025 to August 2026; 1,920 rows per horizon). Model selection used the validation set only; each selected model was then retrained on training and validation data and evaluated once on the test set.

**Baselines and models.** Four baselines were computed: persistence, seasonal naive, climatology (the reservoir's median for the target month) and persistent anomaly. Three model families were tuned on a small grid (90 configurations in total): ridge regression, random forest (300 trees) and histogram gradient boosting, each wrapped in a scikit-learn pipeline with its preprocessing (Pedregosa et al., 2011).

**Metrics and significance.** The main metric is the mean absolute error (MAE) of the filling ratio, complemented by RMSE, NSE and KGE. The skill score uses as reference the best baseline on the validation set. The significance of the gain over that reference was tested with a block bootstrap resampling whole target months (2,000 replicates), a simplified form of the Diebold-Mariano test (Diebold & Mariano, 1995) that respects the correlation between reservoirs. Errors were also analysed by target month and by reservoir size.

**Value of rainfall information.** To bound the value of seasonal rainfall forecasts, an "oracle" model was given the rainfall actually observed between t + 1 and t + h; it cannot be deployed but shows the maximum gain a perfect rainfall forecast could bring.

**Spatial generalisation.** A five-fold cross-validation grouped by reservoir, on target months up to 2024, measured performance on reservoirs absent from training.

## 3.9 Uncertainty and early warning

Prediction intervals were obtained by two gradient-boosting models with quantile losses (α = 0.10 and 0.90), corrected by conformalized quantile regression calibrated on the validation year (Romano et al., 2019). They were evaluated by their coverage (PICP, target 80 %) and mean width (MPIW).

The early warning targets the event "filling ratio below 0.20". A histogram gradient-boosting classifier with balanced class weights was compared with two rules: persistence (alert if already critical) and the regression rule (alert if the forecast is below the threshold). The decision threshold was chosen on the validation set by maximising the F1 score. Evaluation used ROC-AUC, PR-AUC, the Brier score, precision, recall and F1, a reliability diagram, and the detection of entries into crisis (reservoirs above the threshold at t and below it at t + h). An isotonic recalibration was kept only if it improved the Brier score on the second half of the validation year. Permutation importance on the test set was used to explain the selected model.

## 3.10 Final model, deployment and tools

The selected configuration was retrained on all data and saved as a single bundle (median regressor, quantile models with their conformal correction, alert classifier and threshold, climatologies and reference areas), together with a model card and the test scores. The bundle is reloaded from disk and its predictions checked against the in-memory model. The API's monthly update uses the same forecasting function (`ml/forecasting.py`) and maps forecasts to the application's statuses: dried up if the forecast filling is below 5 %, at risk if the probability of a critical level is at least 50 %, active otherwise.

The analysis used Python 3.11.9 with numpy 2.4.6, pandas 3.0.2, scikit-learn 1.9.0, GeoPandas 1.2.0 and the Earth Engine API 1.7.42. The random seed was fixed, satellite extractions were cached, and a fingerprint of the final data panel is recorded in the model card. The application itself runs on FastAPI with a PostgreSQL/PostGIS database and a React frontend (Appendix C).

## 3.11 Ethical considerations

The project uses only open, aggregated environmental data; no personal data were collected. The main ethical risk is that of over-confident information reaching decision-makers in a humanitarian context. Three measures address it: every forecast is published with its uncertainty, the model card states the intended and non-intended uses, and the report and notebook state the limits openly, including negative results.
