@section prelim

# Abstract

Small reservoirs are the backbone of dry-season water supply for livestock, market gardening and domestic use around Ouagadougou, Burkina Faso, yet almost none of them is gauged. This project asks whether free satellite archives can provide a reliable monthly measurement of each reservoir and a useful forecast of its state one to three months ahead. A reproducible pipeline built on Google Earth Engine measures the monthly water area of 100 water bodies at 10 m resolution from January 2019 to August 2026, fusing cloud-masked Sentinel-2 imagery with calibrated Sentinel-1 radar, and relates it to CHIRPS rainfall and ERA5-Land climate data. The previous production model was audited first: its reported score (R² = 0.19) became negative (−0.45) under an honest temporal split, and an inference bug made its served predictions unrelated to the model. Under a strict temporal validation, a random forest forecasts the filling ratio one month ahead with a mean absolute error of 0.108, 19.6 % better than reservoir climatology (block-bootstrap p < 0.001); at two and three months it only matches climatology, and an oracle experiment shows that even perfect rainfall knowledge would not help. Conformal intervals reach 80-83 % coverage at one and two months, and an early-warning classifier detects 70-80 % of entries into a critical state with 83-90 % precision. The system's value therefore lies in measuring and anticipating the dry-season drawdown, which points to dry-season irrigation and livestock water planning as the most relevant use.

**Keywords:** small reservoirs; Sentinel-2; Sentinel-1; Google Earth Engine; water-surface monitoring; forecasting; early warning; Sahel; Burkina Faso.

# List of Figures

@list Figure

# List of Tables

@list Table

# List of Acronyms

@acronyms
API | Application Programming Interface
APA | American Psychological Association
AUC | Area Under the Curve
CHIRPS | Climate Hazards Group InfraRed Precipitation with Station data
CI | Confidence Interval
CQR | Conformalized Quantile Regression
DEM | Digital Elevation Model
DGRE | Direction Générale des Ressources en Eau (Burkina Faso water resources directorate)
ERA5-Land | ECMWF Reanalysis v5, land component
FDR | False Discovery Rate
GEE | Google Earth Engine
GIS | Geographic Information System
HGB | Histogram-based Gradient Boosting
IP | Independent Project
JRC | Joint Research Centre (European Commission)
KGE | Kling-Gupta Efficiency
MAE | Mean Absolute Error
MNDWI | Modified Normalized Difference Water Index
MPIW | Mean Prediction Interval Width
NDVI | Normalized Difference Vegetation Index
NDWI | Normalized Difference Water Index
NGO | Non-Governmental Organisation
NSE | Nash-Sutcliffe Efficiency
ONEA | Office National de l'Eau et de l'Assainissement (national water utility)
OSM | OpenStreetMap
PET | Potential Evapotranspiration
PICP | Prediction Interval Coverage Probability
PR-AUC | Area under the Precision-Recall curve
RMSE | Root Mean Square Error
ROC | Receiver Operating Characteristic
RQ | Research Question
S1 / S2 | Sentinel-1 / Sentinel-2
SAR | Synthetic Aperture Radar
SRTM | Shuttle Radar Topography Mission
SWIR | Short-Wave Infrared
SWOT | Surface Water and Ocean Topography mission
UTM | Universal Transverse Mercator
VV | Vertical transmit, vertical receive (radar polarisation)

# Acknowledgements

I would like to thank [supervisor's name], my faculty advisor at TamTam Digital School, for the guidance and critical feedback given throughout this Independent Project, and the teaching staff of the [academic program] for the training on which this work relies.

This project would not have been possible without open data and open software. I am grateful to the European Space Agency and the Copernicus programme for the Sentinel-1 and Sentinel-2 archives, to Google for the Earth Engine platform and the Cloud Score+ dataset, to the Climate Hazards Center (UC Santa Barbara) for CHIRPS, to ECMWF for ERA5-Land, to the European Commission's Joint Research Centre for the Global Surface Water dataset, and to the OpenStreetMap contributors who mapped the water bodies of the Ouagadougou region. I also thank the developers of the scientific Python ecosystem (pandas, scikit-learn, GeoPandas) on which every analysis in this report is built.

[Add any personal acknowledgements: family, classmates, partners met during the project.]

# Executive Summary

**The problem.** Around Ouagadougou, several dozen small reservoirs supply water for livestock, dry-season market gardening and, in places, domestic use. Apart from the large dams operated for the city's drinking water, none of them is gauged. Managers (water agencies, NGOs, agricultural and livestock services) have no consolidated view of which reservoirs are full, falling or nearly dry, and usually discover a drying-up after it has happened. Field visits to dozens of sites are costly and, in the current security context, often impossible.

**What was done.** The WaterTracker application already displayed a risk status for 65 water points, produced by a first model. This project audited that model, then rebuilt the analytical core. A reproducible notebook extracts from Google Earth Engine the monthly water area of 100 water bodies (the 44 physical reservoirs behind the application's water points plus 56 water bodies of 10 ha or more that were missing from the inventory) at 10 m resolution from January 2019 to August 2026. It fuses cloud-masked Sentinel-2 imagery with calibrated Sentinel-1 radar, relates the series to rainfall and climate, and trains forecasting models that are evaluated on years they never saw.

**Key findings.**
- The previous model's published score did not survive an honest evaluation (R² from 0.19 to −0.45), and a software bug made its served predictions unrelated to the model. The redesign was therefore necessary.
- The satellite measurement is robust: 98.7 % of reservoir-months are observed directly by Sentinel-2; results barely change with the water-index threshold.
- By April, the median reservoir is dry every year, whatever the rainfall of the previous season: wetter rainy seasons raise the peak (ρ = 0.32) but not the dry-season minimum (ρ = 0.05).
- One month ahead, the random forest beats the reservoir's own climatology by 19.6 % (MAE 0.108 versus 0.134, p < 0.001), with its smallest errors from October to March. Two and three months ahead, it only matches climatology, and knowing future rainfall perfectly would not improve it.
- The early-warning classifier detects 70-80 % of reservoirs entering a critical state (below 20 % of their reference area), with 83-90 % of alerts confirmed.

**What it means.** The system's value is not a long-range prediction but a reliable monthly measurement and a one-month anticipation of the dry-season drawdown. The most relevant users are therefore those who plan dry-season water use across many sites: irrigation and livestock programmes, NGOs and water agencies.

**Recommendations.** Refocus the product on two dry-season deliverables (an end-of-rainy-season assessment and a monthly drawdown update with alerts); add a climatological alert baseline and an "expected drying-up month" output; remove the legacy text recommendations built on the old model; validate the measurements in the field with a partner; and run a pilot over the 2026-2027 dry season to measure whether the information changes decisions.

@toc

@section main

# 1. Introduction

## 1.1 Problem Statement

Burkina Faso is a Sahelian country with a single rainy season, from June to October, followed by seven to eight months with almost no rain. To store water from one season to the next, the country has built a large number of small dams and reservoirs: at least 1,700 small reservoirs had been constructed by the end of the 2000s, most of them in the previous thirty years (Boelee et al., 2009). They support dry-season irrigation, livestock watering, fishing and domestic use, and are a central element of rural livelihoods (Venot et al., 2012).

Despite their importance, these reservoirs are poorly known. Inventories are incomplete and rarely up to date, and the storage of most reservoirs is simply not measured (Liebe et al., 2005; Venot et al., 2012). Around Ouagadougou, only the large dams that supply the capital's drinking water are monitored by the national water utility. The small and medium reservoirs used by farmers and herders have no staff gauge and no regular survey. Their managers, in practice water agencies, agricultural and livestock services, municipalities and NGOs, therefore have no consolidated view of the resource. They usually learn that a reservoir has dried up when it has already happened, and react in emergency: water trucking, forced livestock movements, lost market-garden harvests. Monitoring by field visits is costly when dozens of sites are involved and, in the current security context, often impossible.

Satellite remote sensing offers an alternative. The Sentinel-2 optical and Sentinel-1 radar missions observe every reservoir every few days at 10-20 m resolution, free of charge, and platforms such as Google Earth Engine make these archives usable without local infrastructure (Gorelick et al., 2017). The WaterTracker application was created to exploit this opportunity: it displays the water points around Ouagadougou on a map, with a risk status for each one. Its first analytical model (v2), however, relied on a half-yearly water index measured at a single point per reservoir, and its reported performance had never been checked against an honest evaluation.

The problem addressed by this Independent Project is therefore twofold. Scientifically, it is to determine whether free satellite data can produce a reliable monthly measurement of each reservoir and a forecast of its state one to three months ahead that is better than what a manager could guess from the usual seasonal cycle. Practically, it is to give WaterTracker an analytical core whose outputs can be trusted by the people who have to allocate scarce resources before the dry season becomes a crisis. The significance of the problem lies in the gap between the importance of these reservoirs and the absence of information about them: any reliable, low-cost monitoring would be an improvement over the current situation, provided that its limits are clearly stated.

## 1.2 Literature Review

**Small reservoirs in the Sahel.** Small reservoirs have been promoted across sub-Saharan Africa as a low-cost way to secure water for agriculture and livestock. Venot et al. (2012), drawing on cases from Burkina Faso, Ghana, Ethiopia and Zambia, show that their actual costs, performance and governance are often worse than assumed, partly because so little is known about how they function once built. In Burkina Faso, even the number of reservoirs is uncertain: Boelee et al. (2009) report that at least 1,700 small reservoirs have been built, and the lack of up-to-date inventories is repeatedly cited as a key obstacle to their management. This information gap is the starting point of the present work.

**Sahelian hydrology.** The filling of Sahelian reservoirs depends on runoff, which responds non-linearly to rainfall. Mahé and Paturel (2009) documented the "Sahelian paradox": since the 1970s, runoff coefficients of Sahelian rivers have increased even though rainfall remained below its pre-drought level, mainly because of land-cover change. The amount of rain is therefore an imperfect predictor of how much water reaches a reservoir. Gal et al. (2016) used satellite-derived lake areas combined with a height-area-volume model to estimate inflows over ungauged Sahelian watersheds, illustrating how remote sensing can substitute for missing gauges. During the dry season, reservoirs lose water through open-water evaporation, which is very high in the Sahel, through infiltration and through withdrawals; the relative importance of these terms varies from one reservoir to another and is rarely measured.

**Remote sensing of surface water.** Open water absorbs strongly in the near and short-wave infrared, which makes it easy to separate from land with normalised difference indices. McFeeters (1996) introduced the NDWI, based on green and near-infrared bands; Xu (2006) proposed the MNDWI, which replaces the near-infrared with the short-wave infrared (SWIR) and better separates water from built-up areas and bare soil, a frequent confusion in the Sahel. Because the Sentinel-2 SWIR band has a 20 m resolution, Du et al. (2016) showed that sharpening it to 10 m before computing the MNDWI produces accurate water maps at 10 m. At the global scale, Pekel et al. (2016) used three decades of Landsat imagery to map the occurrence and seasonality of surface water at 30 m (JRC Global Surface Water); this dataset is retrospective and too coarse for small reservoirs, but it is a valuable reference to locate water bodies and check inventories. Clouds are the main obstacle during the rainy season: scene-level cloud filters discard most images from July to September, while pixel-level quality scores such as Cloud Score+ (Pasquarella et al., 2023) keep the clear parts of each image. Synthetic Aperture Radar (SAR) sees through clouds: smooth open water reflects the radar signal away from the sensor and appears dark. Annor et al. (2009) delineated small reservoirs in northern Ghana with radar imagery, and the Sentinel-1 mission (Torres et al., 2012) now provides free radar data with a regular revisit. Radar is, however, sensitive to wind roughening and confuses water with very dry sandy soils, so radar-derived areas need local calibration.

**From area to volume.** Satellites measure an area, not a volume. Liebe et al. (2005) surveyed the bathymetry of 61 small reservoirs in the Upper East Region of Ghana, a landscape similar to the central plateau of Burkina Faso, and derived a power-law relationship between surface area and volume, valid for reservoirs of 1 to 35 ha. Rodrigues et al. (2012) applied the same approach in the Brazilian savannah and estimated the total storage of 147 small reservoirs from Landsat images. Such relationships give orders of magnitude only; precise volumes require bathymetry or altimetry, which the SWOT mission now provides for larger water bodies (Biancamaria et al., 2016).

**Forecasting and its evaluation.** Forecasting literature insists that a model must be compared with simple references: persistence, seasonal naive forecasts and climatology (Hyndman & Athanasopoulos, 2021). In hydrology, model performance is commonly summarised by the Nash-Sutcliffe efficiency (Nash & Sutcliffe, 1970) and by the Kling-Gupta efficiency, which decomposes the error into correlation, bias and variability (Gupta et al., 2009). Tree ensembles such as random forests (Breiman, 2001) and gradient boosting (Ke et al., 2017) are strong learners for tabular data. Their evaluation, however, is easily biased: when observations are correlated in time or space, random cross-validation overestimates performance, and blocked or grouped schemes are required (Roberts et al., 2017); more generally, any information from the future that enters the features or the preprocessing produces "leakage" and optimistic results (Kaufman et al., 2012). Comparing two forecasts requires a significance test adapted to correlated errors (Diebold & Mariano, 1995). For decision-making, a forecast must also carry its uncertainty: conformalized quantile regression (Romano et al., 2019) produces prediction intervals with guaranteed coverage under mild assumptions, and probabilistic alerts are judged by their calibration and Brier score (Brier, 1950). Finally, responsible deployment calls for documenting a model's intended use, performance and limits in a "model card" (Mitchell et al., 2019).

**Gap.** The literature provides each building block (water indices at 10 m, radar gap-filling, area-volume relationships, honest forecast evaluation), but they are rarely combined into an operational, monthly, reservoir-by-reservoir monitoring and forecasting system for small Sahelian reservoirs, evaluated against strong baselines. Global datasets are retrospective, and studies of small reservoirs usually stop at mapping or storage estimation. Whether such a system can forecast reservoir states better than climatology, and for which decisions it is useful, remains an open, practical question. This project addresses it for the reservoirs around Ouagadougou.

## 1.3 Objectives

The general objective is to provide WaterTracker with a reliable, reproducible and honestly evaluated analytical core for monitoring and forecasting small reservoirs around Ouagadougou.

The specific objectives are to:
- audit the previous production model (v2) and quantify its weaknesses;
- build a quality-controlled inventory of the reservoirs in a 50 km radius around Ouagadougou;
- produce a continuous monthly series of water area at 10 m for each reservoir from 2019 onwards, by fusing optical and radar data;
- describe the reservoirs' seasonal and inter-annual dynamics and their response to rainfall;
- forecast each reservoir's filling ratio one to three months ahead, with calibrated uncertainty, and compare it with strong baselines;
- issue a probabilistic early warning of a critical level and evaluate it on entries into crisis;
- package the final model so that the application can serve monthly forecasts, and document its limits.

The four research questions and their testable hypotheses are summarised in [[tab:rq]].

@table Research questions and hypotheses {#tab:rq}
Question | Hypothesis | Test
RQ1 (hydrology): What are the seasonal and inter-annual dynamics of the reservoirs' water area, and how do they respond to rainfall? | H1: the water area follows a single annual cycle driven by the rainy season, responds to rainfall within one month, and wetter rainy seasons lead to higher filling. | Cross-correlation; Spearman correlations; Mann-Kendall trends with FDR control
RQ2 (remote sensing): Can Sentinel-2 / Sentinel-1 fusion produce a continuous monthly series despite rainy-season clouds? | H2: a usable value is obtained for at least 95 % of reservoir-months, and the measurement is robust to the index threshold and to resolution. | Share of reliable months; independent validation of the radar fill; sensitivity analyses
RQ3 (AI): Can the filling ratio be forecast one to three months ahead better than simple baselines, and with what uncertainty? | H3: a machine-learning model beats the strongest baseline at each horizon with a significant gain (p < 0.05) and calibrated 80 % intervals. | Temporal validation; MAE, NSE, KGE, skill; block bootstrap; conformal coverage
RQ4 (operations): Can a reliable early warning of a critical level be issued? | H4: a probabilistic classifier detects entries into the critical state with ROC-AUC ≥ 0.8 and a better F1 score than persistence. | ROC-AUC, PR-AUC, Brier, F1; evaluation on entries into crisis

**Scope.** The study covers a 50 km radius around Ouagadougou (about 7,700 km²) and the period January 2019 to August 2026. It measures water area, not water quality, and estimates volume only as an order of magnitude. User needs were not surveyed during the project; the recommendations on the target users are derived from the results and must be validated with stakeholders.

**Stages of the project.** The project followed the iterative stages set by the IP guidelines ([[fig:stages]]): the problem was defined from the gap between the importance of the reservoirs and the absence of data, and sharpened by the audit of the existing model; research questions and hypotheses were then formulated; the literature was reviewed to choose the methods; the methodology was implemented in a reproducible notebook; finally, the results were analysed against the hypotheses and turned into recommendations.

@figure docs/independent-project/figures/fig00b_project_stages.png | Project workflow diagram: stages of the Independent Project {#fig:stages}
