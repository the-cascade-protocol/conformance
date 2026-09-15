# Third-party attribution notices

The fixtures and the reference patient pod in this repository carry codes from
external terminologies. The notices below are required by, or acknowledge, those
sources. They apply in addition to `LICENSE`, which covers this project's own
material.

## SNOMED CT (SNOMED International)

Fixtures and the reference patient pod carry SNOMED CT concept identifiers with
their terms. What is redistributed here is identifiers and terms only: no
relationships, hierarchies, refsets, maps, or bulk description sets, which are
outside the Global Patient Set and are not present in this repository.

> This material includes SNOMED Clinical Terms® (SNOMED CT®) concept identifiers
> and terms from the SNOMED CT Global Patient Set, released by SNOMED
> International under Creative Commons Attribution-NoDerivatives 4.0
> (https://creativecommons.org/licenses/by-nd/4.0/). SNOMED and SNOMED CT are
> registered trademarks of SNOMED International.

The Global Patient Set covers International Edition concepts. US Edition
extension concepts are outside it. A fixture that acquires a US-extension code,
for example from a vendor-pulled sample, needs an International Edition code in
its place or belongs in a private corpus. Codes already here have not been
audited against that boundary one by one; doing so is open work.

## LOINC (Regenstrief Institute)

Fixtures and the reference patient pod carry LOINC codes with their display
names. Section 8 of the LOINC license does not require a notice for LOINC codes
used in electronic records and messages alongside test results and clinical
observations, which is what a fixture is. This notice is given anyway, because
the repository also documents LOINC codes outside instance data:

> This material contains content from LOINC (http://loinc.org). LOINC is
> copyright © Regenstrief Institute, Inc. and the Logical Observation Identifiers
> Names and Codes (LOINC) Committee and is available at no cost under the license
> at http://loinc.org/license. LOINC® is a registered United States trademark of
> Regenstrief Institute, Inc.

## ICD-10-CM (CDC / CMS)

ICD-10-CM is a U.S. Government work in the public domain. Reference:
https://www.cms.gov/medicare/coding-billing/icd-10-codes

## RxNorm (U.S. National Library of Medicine)

RxNorm identifiers appearing in fixtures come from `SAB=RXNORM` content, which
NLM releases without restriction.

> This product uses publicly available data courtesy of the U.S. National Library
> of Medicine (NLM), National Institutes of Health, Department of Health and Human
> Services. NLM is not responsible for the product and does not endorse or
> recommend this or any other product.
