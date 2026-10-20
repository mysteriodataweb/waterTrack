# 4. Results and Analysis

## 4.1 Audit of the previous model (v2)

The audit confirmed three of the four suspected problems ([[tab:audit]]). The half-yearly target was largely determined by the season: in the dry season the mean point NDWI was 0.08, almost always below the 0.2 threshold, and a rule that predicts the most frequent target value of each season, with no learning, was right 55.6 % of the time. The published score of the model (R² = 0.19 with a random split) became negative under a temporal split (R² = −0.45; MAE rising from 4.9 to 8.6 half-years), meaning that the model forecast worse than a constant mean ([[fig:v2]]); removing the leaking feature changed little, which shows that the inflated score came mainly from the autocorrelation between rows. Most seriously, the API scaled the inputs before passing them to a model trained on raw values: the served predictions differed from the model's own by 6.07 half-years on average, and only 0.4 % of them were identical after rounding. The fourth point was qualified: across half-years the point NDWI followed the new filling ratio (median within-reservoir correlation 0.83), but within dry seasons only, which is what an alert needs, the median correlation fell to 0.39 and 60 % of reservoirs were below 0.5.

@table Results of the audit of the v2 model {#tab:audit}
Problem | Test | Result | Verdict
D1 Seasonal target | Accuracy of a season-only rule | 55.6 % | Confirmed
D2 Information leak | R² random split vs temporal split | 0.19 vs −0.45 | Confirmed
D3 Training/inference mismatch | Mean gap correct vs served prediction | 6.07 half-years; 0.4 % identical | Confirmed (most serious)
D4 Point NDWI vs water area | Median within-reservoir correlation, all / dry season only | 0.83 / 0.39 | Qualified

@figure docs/independent-project/figures/fig_v2_audit.png | Score of the previous model (v2) under a random and a temporal split {#fig:v2}

These results justified replacing the whole chain rather than tuning the old model: the variable (a point index), the time step (half-yearly), the target (a censored count of periods) and the deployment code all had to change.

## 4.2 Inventory and measurement quality (RQ2)

The 65 water points of the application corresponded to 44 physical reservoirs: 12 water bodies were shared by two to five points. Compared with the JRC reference, the application's inventory covered only 38 % of the water bodies of 10 ha or more, but 76 % of their area: the large reservoirs were known, while many medium-sized ones, up to 273 ha, were missing. Adding the 56 missing water bodies brought the study to 100 analysis regions; 96 of them had a reference area of at least 2 ha and were modelled.

Measurement quality was high ([[tab:quality]]). Thanks to pixel-level cloud masking, 98.7 % of the 9,200 reservoir-months had a reliable optical observation; even in August, the cloudiest month, 88 % were reliable. Radar was therefore needed for less than 1 % of the months. Its threshold was set at −20 dB (median correlation with optical areas per reservoir 0.64), and a usable calibration was obtained for 64 of the 100 reservoirs. On independent months, the radar reconstruction was coarse (MAE 8.2 ha, median relative error 55 %), which is acceptable only because it fills so few values. After fusion, every month of every modelled reservoir had a value: 98.7 % from Sentinel-2, 0.8 % from radar and 0.5 % interpolated.

@table Measurement quality indicators {#tab:quality}
Indicator | Value
Reservoir-months with a reliable optical observation | 98.7 % (August: 88 %)
Final provenance: Sentinel-2 / Sentinel-1 / interpolation | 98.7 % / 0.8 % / 0.5 %
Radar reconstruction on independent months: MAE, median relative error | 8.2 ha, 55 %
Filling ratio, MNDWI threshold −0.1 / +0.1: correlation with threshold 0 | 0.986 / 0.961
Filling ratio, MNDWI threshold −0.1 / +0.1: mean absolute difference | 0.034 / 0.039
20 m vs 10 m area difference (median): < 5 ha / 5-50 ha / > 50 ha | 4.3 % / 1.2 % / 0.4 %
Sharpened MNDWI vs native 10 m NDWI: median temporal correlation | 0.83

The measurement was robust to methodological choices. Moving the MNDWI threshold by ±0.1 changed the filling ratio by only 0.03-0.04 on average (correlations 0.96-0.99). Working at 10 m instead of 20 m made little difference for large water bodies but mattered for the smallest ones (median difference 4.3 %, up to 27 %, below 5 ha). The sharpened MNDWI followed the native 10 m NDWI closely in time (median correlation 0.83), while the NDWI detected about 20 % less water overall, consistent with its known weakness on turbid water. H2 is supported.

## 4.3 Hydrological dynamics (RQ1)

All reservoirs share a single, regular annual cycle ([[fig:total]], [[fig:regime]]). Filling starts in June-July, peaks in August (median filling ratio 0.94) and is followed by a long drawdown. By March-April, the median reservoir is empty, and 89 % of the reservoirs are below the critical level of 20 % in April, compared with 3-4 % in August-September. Summed over the 96 reservoirs, the water area falls to 34-43 km² at the end of each dry season and climbs back to 97-108 km² at the peak; the indicative stored volume of the 53 reservoirs of 1 to 35 ha ranges from 16.8 million m³ in August to 0.3 million m³ in April ([[fig:volume]]).

@figure backend/reports/figures/fig05_total_area_rain.png | Total water area of the 96 modelled reservoirs (line, km²) and monthly CHIRPS rainfall (bars, inverted axis), January 2019 - August 2026. Labels in French from the notebook run. {#fig:total}

@figure docs/independent-project/figures/fig_regime.png | Mean regime of the modelled reservoirs: distribution of the filling ratio by calendar month (top) and share of reservoirs below the critical level (bottom) {#fig:regime}

@figure docs/independent-project/figures/fig_volume.png | Indicative stored volume of the 53 reservoirs within the domain of validity of the Liebe et al. (2005) relationship {#fig:volume}

Reservoirs respond quickly to rainfall: the correlation between monthly rainfall and the change in filling peaks at lag 0 (median r = 0.49) and is already weak at lag 1 (0.18). The drawdown accelerates through the dry season, from about 6 points of filling ratio per month in November-December to 13-15 points per month in January-February, while potential evaporation rises from about 330 to 415 mm per month.

The relationship between rainfall and the following dry season is the most striking result. Wetter rainy seasons give higher peaks (Spearman ρ = 0.32, p ≈ 10⁻¹⁷), but they do not predict the dry-season minimum (ρ = 0.05, p = 0.2): in every hydrological year from 2019 to 2025, the median reservoir reached a minimum filling of zero. The size of the reservoir matters more: larger reservoirs keep more water at the end of the dry season (ρ = 0.38, p = 0.0001), although almost every reservoir below about 100 ha reaches a near-zero minimum. Finally, a few reservoirs showed nominal trends in their dry-season minimum, but none remained significant after correction for multiple testing (0 of 72). H1 is therefore partly supported: the cycle and the fast response are confirmed, but the amount of rain does not carry over to the dry-season minimum, and no degradation trend can be claimed over seven years.

## 4.4 Forecast accuracy (RQ3)

On the validation year, climatology was the strongest baseline at every horizon (MAE 0.134), far ahead of persistence (0.164 at one month and 0.343 at three months); during the rainy season the area can double within a month, which makes persistence a weak reference. The random forest, predicting the level rather than the change, was the best model at every horizon. [[tab:test]] and [[fig:mae]] give the results on the test period (2025 to August 2026), which played no part in any choice.

@table Test-set performance (target months 2025 - August 2026; 1,920 forecasts per horizon) {#tab:test}
Model | MAE h=1 | MAE h=2 | MAE h=3 | NSE h=1 | NSE h=3 | Skill h=1 | Skill h=3
Persistence | 0.186 | 0.326 | 0.424 | 0.45 | −0.90 | −38.5 % | −215.7 %
Seasonal naive | 0.133 | 0.133 | 0.133 | 0.68 | 0.68 | +0.6 % | +0.6 %
Climatology (reference) | 0.134 | 0.134 | 0.134 | 0.68 | 0.68 | 0 % | 0 %
Persistent anomaly | 0.133 | 0.165 | 0.170 | 0.66 | 0.55 | +0.7 % | −26.6 %
Ridge | 0.125 | 0.146 | 0.146 | 0.75 | 0.71 | +6.8 % | −8.4 %
Random forest | 0.108 | 0.133 | 0.130 | 0.80 | 0.75 | +19.6 % | +3.4 %
Gradient boosting (HGB) | 0.108 | 0.135 | 0.133 | 0.79 | 0.73 | +19.4 % | +1.0 %

@figure docs/independent-project/figures/fig_test_mae.png | Forecast error on the test period by model and horizon {#fig:mae}

One month ahead, the random forest reduced the MAE from 0.134 to 0.108, a skill of +19.6 %, with NSE and KGE of 0.80. The block bootstrap confirmed that this gain is robust: 0.026 (95 % CI 0.016 to 0.036, p < 0.001). Two and three months ahead, the gain was small and not significant (+0.9 %, p = 0.41; +3.4 %, p = 0.11): the model only matched climatology ([[fig:skill]]). The linear ridge model was clearly worse than the tree ensembles, which indicates non-linear relationships between state, season and forcings. Note that the seasonal naive forecast was marginally better than climatology on the test period (0.1335 versus 0.1342), although climatology had been the better baseline on validation; the conclusions are unchanged.

@figure docs/independent-project/figures/fig_skill.png | Gain of the random forest over climatology, with 95 % block-bootstrap confidence intervals {#fig:skill}

The error varies strongly with the season ([[fig:month]]). It is smallest during the dry season, with an MAE of about 0.04 to 0.09 one month ahead from October to March, and largest from June to August, when the filling depends on the onset of the rains. One month ahead, the model beats climatology in every month except April and May, when most reservoirs are dry and all methods are equivalent; its relative advantage is largest from October to February, roughly 30 to 50 % lower error. Small reservoirs had a slightly higher mean error than large ones (0.122 versus 0.100), with similar medians (about 0.06).

@figure backend/reports/figures/fig12_error_by_month.png | Test MAE by target month for persistence (grey), climatology (yellow-green) and the random forest (purple), at 1, 2 and 3 months. Labels in French from the notebook run ("mois" = month). {#fig:month}

The oracle experiment gave a clear negative answer. Giving the model the rainfall actually observed over the forecast window did not reduce the error at any horizon (changes of −0.8 %, −1.0 % and −1.2 %, i.e. noise). Monthly rainfall totals over the sub-basin do not explain the residual error, so integrating seasonal rainfall forecasts would not improve this model.

Finally, the model generalised to reservoirs it had never seen. In the cross-validation grouped by reservoir, its MAE (0.106, 0.130 and 0.136 at one, two and three months, with a standard deviation of 0.006 to 0.011 across folds) stayed close to its test MAE and below both persistence (0.172 to 0.382) and climatology (0.147 to 0.149). H3 is supported at one month only.

## 4.5 Uncertainty and early warning (RQ4)

The raw quantile intervals were too narrow, covering only 68 to 70 % of the observations for a nominal 80 % ([[tab:intervals]]). After the conformal correction, coverage reached 83 % at one month and 80 % at two months, but remained below nominal at three months (75 %), as the test years differed from the validation year. The 80 % intervals are wide, 0.33 to 0.40 filling points, which reflects the genuine uncertainty of a monthly forecast.

@table Coverage and width of the 80 % prediction intervals on the test set {#tab:intervals}
Horizon | Raw quantile: coverage | Raw quantile: width | Conformalised: coverage | Conformalised: width
1 month | 70.2 % | 0.274 | 83.4 % | 0.333
2 months | 68.0 % | 0.365 | 80.2 % | 0.402
3 months | 69.7 % | 0.394 | 74.9 % | 0.403

The alert classifier discriminated very well between critical and non-critical situations (ROC-AUC 0.96-0.97, PR-AUC 0.94-0.95, for an event rate of 40 %), and its probabilities were well calibrated ([[fig:reliab]]); isotonic recalibration degraded the Brier score on validation and was not kept. Its F1 score (0.89, 0.83 and 0.85 at one, two and three months) was far above persistence (0.77, 0.57 and 0.40), and slightly above the regression rule (0.88, 0.81 and 0.85) ([[fig:alerts]]). On the more demanding test of entries into crisis, the classifier detected 123 of 175 entries one month ahead (70 %) with 25 false alarms, and 374 of 468 three months ahead (80 %) with 40 false alarms; 83 to 90 % of these alerts were confirmed. H4 is supported, with one caveat discussed below: critical situations are strongly seasonal, and a climatological alert rule was not evaluated.

@figure docs/independent-project/figures/fig_alerts.png | Early-warning performance on the test set: F1 score by method (left) and detection of entries into crisis (right) {#fig:alerts}

@figure backend/reports/figures/fig14_reliability.png | Reliability diagram of the alert probabilities on the test set (forecast probability vs observed frequency). Labels in French from the notebook run. {#fig:reliab}

## 4.6 Explainability

Permutation importance agrees with the physical expectations ([[fig:imp]]). One month ahead, the current filling and the target-month climatology dominate, followed by recent rainfall and its climatology. Three months ahead, the current filling becomes almost irrelevant and the target-month climatology carries nearly all of the information: the model behaves as a refined climatology, which explains why it cannot beat climatology at that horizon.

@figure docs/independent-project/figures/fig_importance.png | Permutation importance of the ten most important features of the random forest, one and three months ahead {#fig:imp}

## 4.7 Operational forecast

The final bundle (44.6 MB) was reloaded and checked, then used to issue the forecast at the end of August 2026, at the peak of the rainy season. One month ahead, 94 reservoirs were active and 2 at risk; three months ahead, 84 were active, 11 at risk and 1 forecast as dried up. [[fig:fan]] shows the four reservoirs most likely to reach the critical level within three months, with probabilities between 93 and 100 %. The forecasts were exported for the 65 water points of the application (189 rows covering three horizons) and are served by the API and the monthly bulletin.

@figure backend/reports/figures/fig16_forecast_fan.png | Forecast issued at the end of August 2026 for the four reservoirs most likely to become critical within three months: observed filling (grey), forecast (purple) with its 80 % interval, and critical threshold (red). Labels in French from the notebook run. {#fig:fan}

## 4.8 Summary of the hypotheses

[[tab:verdict]] summarises the verdicts.

@table Verdict on the research hypotheses {#tab:verdict}
Hypothesis | Verdict | Main evidence
H1 Hydrological dynamics | Partly supported | Single cycle, response at lag 0 (r = 0.49); rainfall raises the peak (ρ = 0.32) but not the dry-season minimum (ρ = 0.05); no significant trend
H2 Continuous, robust measurement | Supported | 98.7 % reliable optical months, no missing month after fusion; robust to threshold and resolution
H3 Forecast better than the strongest baseline | Supported at 1 month only | Skill +19.6 % (p < 0.001) at 1 month; not significant at 2-3 months; perfect rainfall would not help; coverage 83 / 80 / 75 %
H4 Reliable early warning | Supported, with a caveat | ROC-AUC 0.96-0.97; F1 0.83-0.89 vs 0.40-0.77 for persistence; 70-80 % of entries into crisis detected; climatological alert baseline not tested
