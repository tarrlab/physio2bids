# physio2bids
### Austin Marcus
### Tarrlab @ CMU, October 2018

Converts Siemens physiological recording files (puls, resp, ext) to BIDS format, given matching Siemens DICOM files.  
Usage:
- `python physio2bids.py -d <DICOM-dir> -p <Physio dir> -o <output-directory>`
- DICOM directory selected must contain DICOMs for the same scans as the Physio folder, since matching is done by checking timestamps
- Writes all converted files (tsv and json per physio file) to specified output directory
