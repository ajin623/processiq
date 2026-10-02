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

These figures and categories are source-provided metadata. They have not yet been independently reproduced by the ProcessIQ ingestion pipeline.

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
