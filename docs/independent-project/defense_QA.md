# Defense preparation: likely questions and suggested answers

Answers rely only on results in the report and the notebook. Figures are those of the run of 8 October 2026.

## Problem and relevance

**Why is this problem important?**
Small reservoirs carry dry-season water for livestock, market gardening and domestic use; Burkina Faso has built at least 1,700 of them (Boelee et al., 2009). Around Ouagadougou, only the large city dams are gauged, so managers usually learn that a reservoir has dried up after the fact. Free satellite data can fill that gap at almost no marginal cost.

**Who would use it?**
The results point to people who plan across many sites they cannot visit: irrigation and livestock programmes, NGOs, water agencies. This is an inference from the results; user needs were not surveyed, which is listed as a limitation and as the first next step (a pilot over the 2026-2027 dry season).

**Is it really AI?**
Most of the value comes from remote sensing and data engineering. Machine learning adds a measurable gain at one month (+19.6 % over climatology, p < 0.001) and powers the early warning (ROC-AUC 0.96-0.97). I present it as a satellite monitoring service supported by AI where it makes a measurable difference, not as an "AI project".

## Data and measurement

**How do you handle clouds in the rainy season?**
Pixel-level masking with Cloud Score+ instead of discarding whole scenes; a month is reliable when at least 90 % of the region is observed. 98.7 % of reservoir-months were reliable (August: 88 %). Sentinel-1 radar, calibrated reservoir by reservoir, fills the rest (0.8 %), then short interpolation (0.5 %).

**The radar error is 55 %. Is that acceptable?**
Only because radar fills less than 1 % of the months. It avoids gaps; it is not a precise source. A Bayesian fusion or Sentinel-1C could improve it.

**Why MNDWI and not NDWI?**
MNDWI separates water from built-up areas and bare soil better and handles turbid water (Xu, 2006). The SWIR band was sharpened to 10 m (Du et al., 2016). The native 10 m NDWI was used as a control: median temporal correlation 0.83, with about 20 % less water detected, as expected for turbid water.

**How do you know the measurement is right without ground truth?**
Consistency checks only: threshold sensitivity (±0.1 changes the filling by 0.03-0.04), resolution effect, agreement between sensors and with the JRC dataset. Field validation is the main limitation and a priority next step.

**Why 100 water bodies when the application had 65 points?**
The 65 points were 44 physical reservoirs (12 water bodies were shared by several points). The application's inventory covered 76 % of the JRC water area but only 38 % of the water bodies of 10 ha or more, so 56 missing ones were added.

## Forecasting

**Why compare with climatology rather than persistence?**
Persistence is weak at a monthly step because a reservoir can double within a month in the rainy season. Climatology was the best baseline on the validation year at every horizon; comparing with a weak reference would inflate the skill.

**Why a temporal split?**
Monthly observations are autocorrelated. The audit showed that the previous model's R² of 0.19 under a random split became −0.45 under a temporal split. Training 2019-2023, validation 2024, test 2025 to August 2026, used once.

**Why does the model fail at two and three months?**
At those horizons, the current state carries little information and the target-month climatology dominates (permutation importance 0.138 vs 0.005 for the current filling at three months). The model behaves like a refined climatology.

**Why not add seasonal rainfall forecasts?**
The oracle experiment gave the model the rain actually observed over the forecast window: the error did not improve (−0.8 % to −1.2 %). Monthly rainfall totals do not explain the residual error, consistent with the non-linear runoff response in the Sahel (Mahé & Paturel, 2009).

**Why a random forest?**
It was the best on the validation year at every horizon among ridge, random forest and gradient boosting (90 configurations), and gradient boosting gave almost identical test results. Ridge was clearly worse, which indicates non-linear relationships.

**Is the gain at one month significant?**
Yes: MAE gain 0.026, 95 % CI 0.016 to 0.036, block bootstrap over whole months (p < 0.001). At two and three months: p = 0.41 and p = 0.11.

**Does it work on new reservoirs?**
In cross-validation grouped by reservoir, the MAE was 0.106 / 0.130 / 0.136, below persistence and climatology at every horizon. That supports an extension to neighbouring areas, with local revalidation.

## Uncertainty and alerts

**How reliable are the intervals?**
Conformalised 80 % intervals cover 83 % at one month, 80 % at two months and 75 % at three months (the test years differ from the validation year). They are wide (0.33-0.40), which reflects real uncertainty.

**Isn't the alert just the season?**
Partly, possibly. Critical situations are very seasonal (89 % of reservoirs in April). The demanding test, entries into crisis, gives 70-80 % detected with 83-90 % of alerts confirmed, but a calendar-only alert rule was not evaluated. It is the first methodological addition I would make.

**Why the 20 % threshold?**
Below 20 % of the reference area, usually only a residual pond remains. With the area-volume relationship of Liebe et al. (2005), 20 % of the area is about 10 % of the volume.

## Previous model and engineering

**What was wrong with the previous model?**
A target almost determined by the season (a season-only rule was right 55.6 % of the time), a score inflated by a random split, and an inference bug: the API scaled the inputs of a model trained on raw values, so served predictions differed by 6.07 half-years on average from the model's own.

**How do you prevent that bug from returning?**
The notebook and the API share the same feature module (`ml/features.py`) and the same inference function (`ml/forecasting.py`); preprocessing is serialised inside each scikit-learn pipeline; the saved bundle is reloaded and checked.

## Limits and future work

**What are the main limitations?**
Area, not volume; no ground truth; a short history (five training seasons); unobserved withdrawals; the missing calendar alert baseline; text advice in the app still built on the old model; a single 50 km area.

**What would you do next?**
A pilot with one programme over the 2026-2027 dry season, starting with the October-November assessment; field checks; the calendar baseline and an "expected drying-up month" output; replacing the legacy advice; clarifying Google Earth Engine licensing before any paid offer.
