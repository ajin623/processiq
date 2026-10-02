# BPI Challenge 2019 Structural Profile

## 1. Status

This document records the first independently reproduced structural profile of the ProcessIQ source event log.

- **Profile date:** 2 October 2026
- **Source file:** `data/raw/BPI_Challenge_2019.xes`
- **Profiler:** `processiq.inspect_xes`
- **Profiler method:** Memory-conscious XML streaming
- **Business analysis status:** Not started

The results below describe the dataset's structure and basic field coverage. They are not process-performance findings.

## 2. Reproduced Dataset Size

The profiler independently reproduced:

| Measure | Verified value |
|---|---:|
| Purchase-item traces | 251,734 |
| Events | 1,595,923 |
| Unique activities | 42 |
| Unique non-missing resources | 627 |

These values match the counts stated in the official dataset description.

## 3. Reconciliation Checks

Two completeness reconciliations were performed:

| Check | Calculated total | Expected total | Result |
|---|---:|---:|---|
| Sum of item-category counts | 251,734 | 251,734 traces | Passed |
| Sum of activity counts plus missing activities | 1,595,923 | 1,595,923 events | Passed |

The profiler found:

- 0 events with a missing activity name
- 0 events with a missing timestamp
- 0 events with an invalid timestamp format
- 399,090 events with a missing resource marker

Missing-resource events represent 25.01% of all events.

A missing resource does not automatically mean a defective event. The meaning depends on the activity, source system, automation behaviour, and original logging design.

## 4. XES Metadata

### Root attributes

- `xes.version`: `1849.2016`
- `xes.features`: empty

The unusual XES version value is preserved as source metadata. It has not prevented standards-based XML parsing.

### Declared extensions

- Organizational
- Concept
- Time

### Declared classifiers

- Event Name using `concept:name`
- Resource using `org:resource`

## 5. Trace Attributes

Every trace contains the following 16 attributes:

- `concept:name`
- `Purchasing Document`
- `Item`
- `Item Type`
- `GR-Based Inv. Verif.`
- `Goods Receipt`
- `Source`
- `Purch. Doc. Category name`
- `Company`
- `Spend classification text`
- `Spend area text`
- `Sub spend area text`
- `Vendor`
- `Name`
- `Document Type`
- `Item Category`

Attribute presence does not prove that every value is analytically usable. Value-level quality will be assessed separately.

## 6. Event Attributes

Every event contains the following five attributes:

- `concept:name`
- `time:timestamp`
- `org:resource`
- `User`
- `Cumulative net worth (EUR)`

Some resource attributes contain missing markers even though the attribute itself is present.

## 7. Item Categories

| Item category | Trace count |
|---|---:|
| 2-way match | 1,044 |
| 3-way match, invoice after GR | 15,182 |
| 3-way match, invoice before GR | 221,010 |
| Consignment | 14,498 |
| **Total** | **251,734** |

The dataset is heavily concentrated in the `3-way match, invoice before GR` category. Later analysis must avoid treating the four categories as equally represented.

## 8. Events per Trace

| Measure | Value |
|---|---:|
| Minimum events per trace | 1 |
| Maximum events per trace | 990 |
| Mean events per trace | 6.3397 |

The maximum of 990 events is an extreme structural observation. It may represent a legitimate recurring purchasing process, extensive rework, or another specialised case. It is not automatically an error.

Median and percentile values have not yet been calculated.

## 9. Timestamp Coverage

### Observed range

- **Earliest timestamp:** 26 January 1948 at 22:59 UTC
- **Latest timestamp:** 9 April 2020 at 21:59 UTC

### Events by timestamp year

| Year | Event count |
|---:|---:|
| 1948 | 10 |
| 1993 | 9 |
| 2001 | 22 |
| 2008 | 45 |
| 2015 | 3 |
| 2016 | 6 |
| 2017 | 223 |
| 2018 | 1,550,468 |
| 2019 | 45,135 |
| 2020 | 2 |
| **Total** | **1,595,923** |

A total of 45,455 events, or 2.8482%, occur outside 2018.

The official record describes the dataset's time coverage as 2018. The observed range does not automatically contradict the source description because cases may start before or finish after the principal period.

However, the earliest years require investigation before cycle-time analysis. No timestamp will be deleted, capped, or corrected without evidence.

## 10. Preliminary Data-Quality Questions

The structural profile creates the following investigation questions:

1. Which activities and cases contain timestamps before 2010?
2. Do 2019 events mainly complete cases created during 2018?
3. What explains the two events in 2020?
4. Which activities account for missing resource markers?
5. Is missing-resource behaviour expected for specific automated activities?
6. Why does one trace contain 990 events?
7. Does the extreme trace represent legitimate repetition or problematic rework?
8. Are monetary values consistent with the documented matching categories?

These are questions, not findings.

## 11. Reproduction

Activate the project environment and run:

```bash
python -m processiq.inspect_xes \
  data/raw/BPI_Challenge_2019.xes \
  --output data/interim/xes_profile.json
```

The source dataset and generated interim JSON are excluded from Git.

## 12. Current Conclusion

The XES file is readable and structurally suitable for further analysis.

The official case, event, activity, and resource counts were independently reproduced. Core activity and timestamp fields are complete and parseable.

Resource coverage and timestamp extremes require deeper investigation before process-duration, conformance, or bottleneck metrics can be trusted.

No business-process improvement recommendation has been made at this stage.
