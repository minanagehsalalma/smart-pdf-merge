# smart-pdf-merge

`smart-pdf-merge` is a small Python CLI for merging PDFs when one of the inputs has broken page geometry, usually from scanner/export tools that wrap a normal image inside a gigantic PDF canvas.

Instead of blindly concatenating files, it inspects each page and decides whether to:

- keep the page as-is
- normalize the page onto a standard A4 or Letter canvas
- print the exact reason for that decision

This directly targets cases like:

- an ID or passport scan exported as a PDF page that is physically enormous
- a merged file where one page appears tiny in the viewer because its media box is absurdly large
- mixed scan sources where most pages are sane but one or two are outliers

## What It Does

- merges input PDFs in the exact order you pass them
- detects suspicious page sizes with:
  - an absolute maximum dimension threshold
  - a relative area comparison against the page cohort median
- rebuilds only the suspicious pages onto a standard page size by default
- preserves sane pages unchanged unless you pass `--normalize-all`
- keeps orientation by using portrait or landscape standard pages automatically
- prints a human-readable report for every page

## Install

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python313\python.exe' -m pip install -r requirements.txt
```

## Usage

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python313\python.exe' .\smart_pdf_merge.py `
  ..\passport.pdf ..\Permesso.pdf `
  -o ..\passport-permesso-normalized.pdf
```

Example output:

```text
[NORMALIZE] passport.pdf page 1: 11520.0 x 8085.6pt (160.0 x 112.3in) -> 842 x 595pt at scale 0.07012
  reason: max dimension 11520.0pt exceeds 2000.0pt; page area 93146113pt^2 exceeds cohort median 500990pt^2 by factor 185.93
[KEEP] Permesso.pdf page 1: 595.0 x 842.0pt (8.3 x 11.7in)
Wrote E:\...\passport-permesso-normalized.pdf with 2 pages. Normalized 1 page(s), kept 1 page(s).
```

## Options

- `-o, --output`: output PDF path
- `--paper {a4,letter}`: standard size used for normalized pages
- `--margin`: margin in PDF points for normalized pages
- `--absolute-max-dimension`: suspicious page threshold by max width or height
- `--relative-area-factor`: suspicious page threshold relative to median page area
- `--normalize-all`: normalize every page, not just outliers
- `--quiet`: only print the final summary

## Why This Exists

Many PDF merge tools assume the source PDFs are already sane. They are not. This tool exists for the common real-world case where a scan looks fine by itself but breaks the merged document because the scanner/exporter wrote nonsense page dimensions.

## License

MIT
