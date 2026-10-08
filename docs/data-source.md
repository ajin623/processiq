# Dataset Source and Integrity Record

## 1. Dataset Identity

- **Title:** BPI Challenge 2019
- **Author:** Boudewijn van Dongen
- **Publisher:** 4TU.Centre for Research Data
- **Publication date:** 31 January 2019
- **Time coverage:** 2018
- **DOI:** https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1
- **Dataset page:** https://figshare.com/articles/dataset/BPI_Challenge_2019/12715853
- **Licence:** Creative Commons Attribution 4.0 International
- **Licence URL:** https://creativecommons.org/licenses/by/4.0/

## 2. Dataset Purpose

The dataset represents an anonymised purchase-order handling process from a multinational organisation operating in the coatings and paints industry.

It was published for the BPI Challenge 2019, with particular attention to purchase-to-pay process behaviour and compliance questions.

## 3. Source-Described Structure

According to the official dataset description, the event log contains:

- 76,349 purchase documents
- 251,734 purchase-item cases
- 1,595,923 events
- 42 activities
- 627 recorded users
- 607 human users
- 20 batch users

The source describes four broad purchasing flows:

1. Three-way matching with invoice after goods receipt
2. Three-way matching with invoice before goods receipt
3. Two-way matching without a required goods receipt
4. Consignment

The [structural profile](dataset-profile.md) independently reproduced 251,734 cases, 1,595,923 events, 42 activities, and 627 unique non-missing resources. The full pipeline run on 8 October 2026 also reconciled case/event counts and the four category counts. The purchase-document count and human/batch-user split above remain source-described metadata unless separately verified; resource identifiers are not automatically human/automation labels.

## 4. Local Acquisition Record

- **Download date:** 2 October 2026
- **Download method:** curl through the official Figshare download service
- **Download URL:** https://ndownloader.figshare.com/files/24072995
- **Local filename:** `data/raw/BPI_Challenge_2019.xes`
- **Server-reported filename:** `BPI_Challenge_2019.xes`
- **Server-reported last modification:** 25 July 2020 at 10:01:38 GMT
- **File size:** 728,558,522 bytes
- **Detected format:** XML 1.0 document
- **SHA-256:** `af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`

## 5. Integrity Verification

The local file was checked using:

```bash
stat --printf='File: %n\nBytes: %s\nModified: %y\n' data/raw/BPI_Challenge_2019.xes

file data/raw/BPI_Challenge_2019.xes

sha256sum data/raw/BPI_Challenge_2019.xes
```

The digest above records the original local acquisition. To compare another local copy against that record:

```bash
printf '%s\n' 'af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7  data/raw/BPI_Challenge_2019.xes' | sha256sum --check
```

## 6. Interpretation and Attribution

The source describes 2018 time coverage. The actual structural profile contains timestamps outside 2018, including historical anomalies and a small number of 2020 events. ProcessIQ uses a documented 2018–2019 timing window plus chronology and duration checks; this is an analytical policy, not a claim that every timestamp in the source belongs to that window. See [methodology](methodology.md).

Suggested dataset citation:

> van Dongen, B. (2019). *BPI Challenge 2019*. 4TU.Centre for Research Data. https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1

The source dataset is CC BY 4.0. ProcessIQ transforms its event records and produces derived tables and visualisations; those outputs are project analyses rather than statements from the dataset publisher. Retain source attribution when sharing derived work. The source licence does not assign a licence to the repository's own code.

Raw and generated datasets remain ignored by Git. The committed PBIX contains imported report data and is a separate report artifact; excluding CSVs from Git does not mean the PBIX contains no data.
