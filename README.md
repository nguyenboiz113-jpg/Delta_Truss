================================================================================
  DeltaTruss - README
================================================================================

OVERVIEW
--------
DeltaTruss is a QA tool for comparing TXT output between two versions of
TrussStudio. It automates the process of running both versions, collecting
output files, and generating an Excel report showing differences by section.


FILES
-----
  main.py           - Main application (GUI)
  config.py         - Load/save config to delta_truss_config.json
  xml_builder.py    - Copy project, patch CompatibilityVersion, build XML job
  runner.py         - Launch TrussStudio instances
  comparator.py     - Parse and compare TXT output files by section
  excel_writer.py   - Write comparison results to Excel
  extract.py        - Extract specific output files for manual inspection
  parse.py          - Parse version string from studio directory path


REQUIREMENTS
------------
  - Python 3.8+
  - openpyxl         (pip install openpyxl)
  - PyInstaller      (pip install pyinstaller)  [for building .exe only]

Each Base Directory must contain:
  - Trusses\    (folder with .tdlTruss files)
  - Presets\    (folder with preset files)


HOW TO USE
----------
1. Launch DeltaTruss.exe (or run: python main.py)

2. Add one or more Base Directories using "+ Add Base"
   - Each Base Dir must contain Trusses\ and Presets\ subfolders

3. Set Studio Dir V1 and Studio Dir V2
   - Point to the TrussStudio installation folders
   - Version is auto-detected from the path (e.g. 2026.3.0.49)

4. (Optional) Check "Patch CompatibilityVersion" for V1 and/or V2
   - Patches the .tdlTruss files to match the target version before running

5. Click "Run"
   - Base dirs are sorted heaviest-first (most .tdlTruss files) for efficiency
   - Up to 6 base dirs run in parallel
   - Progress is shown in the log area
   - App waits until all TXT output files are written before comparing

6. When complete, click "Excel" to open the report
   - One sheet per Base Directory
   - One row per truss file
   - One column pair (Diff / %) per section
   - Cells are color-coded: green = no diff, red = has diff
   - "Sections with diff" column lists all differing sections per file

7. (Optional) Extract Files
   - Paste filenames into the Extract box (one per line or space-separated)
   - Select which Base Dir to extract from
   - Click "Extract" to copy matching files into output\diff_files\


OUTPUT STRUCTURE
----------------
  <base_dir>\
    output\
      <ver_v1>\         TXT output from TrussStudio V1
      <ver_v2>\         TXT output from TrussStudio V2
      diff_files\
        <ver_v1>\       Extracted files for V1
        <ver_v2>\       Extracted files for V2
  <parent_of_base_dirs>\
    compare_results.xlsx


CONFIG
------
Settings are saved automatically to delta_truss_config.json in the working
directory. This includes studio paths and base directory list.


BUILD EXE
---------
  cd "C:\path\to\compare-txt-tool-assert"
  python -m PyInstaller --onefile --windowed --name DeltaTruss --hidden-import openpyxl main.py

Output: dist\DeltaTruss.exe


NOTES
-----
- TrussStudio spawns a child process internally and the parent exits early.
  DeltaTruss polls output files every 0.5s and proceeds only when all files
  are present, or when no new files appear for 60 seconds (stall detection).
- If a Base Directory is missing Trusses\ or Presets\, it will be skipped
  and an empty sheet will appear in the Excel report.
- Max 6 base dirs run in parallel. Each base dir launches 2 TrussStudio
  instances (V1 + V2), staggered 3 seconds apart to avoid license conflicts.

================================================================================
