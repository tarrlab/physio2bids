# physio2bids
### Austin Marcus
### Tarrlab @ CMU, October 2018

Converts Siemens physiological recording files (puls, resp, ext) to BIDS format, given matching Siemens DICOM files.  
#### Installation:
- Clone repository
- Assumes default `python` interpreter is `/usr/bin/python` - change hashbang line of `install.py` if not the case on your system
- Run `python install.py`  
#### Use:
- `physio2bids.py -d <DICOM-dir> -p <Physio dir> -o <output-directory> -l <logfile-name>`
- DICOM directory selected must contain DICOMs for the same scans as the Physio folder, since matching is done by checking timestamps
- Writes all converted files (tsv and json per physio file) to specified output directory
- Writes detailed log to specified file in append mode to permit log concatenation in looped use
