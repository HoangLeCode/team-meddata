# Team change requests

Copy this template into the top folder of your team's app repository if `change-requests.md` is missing. If it already exists, add to it; do not replace your teammates' work. Keep your individual evidence and conclusions in `my-audit.md`.

## Claims

Add your name and what you will audit. Choose a different scope from your teammates, or explain the new evidence you will contribute.

| Author | Feature | Number | Distinct scope or new evidence |
| --- | --- | --- | --- |
|Eeshita Wade |County filter|Los Angeles provider locations per 10,000 eligibles| Tested All counties, Los Angeles, San Diego, All counties with All specialties; independently recalculated LA's rate from cleaned inputs|
| Ziheng Zhang | Priority County Table | Statewide Median | Verified the five lowest-ranked counties, checked the statewide median using provider_analysis.py, and exported the table as CSV. |
| Angana Shah | Provider specialty filter | Provider records missing specialty | Selected Allergy and documented the map failure; independently recalculated the 63.87% missing-specialty metric from cleaned provider data. |
## Requests

Copy this block for each actionable finding and choose a unique ID. Reference that ID in your individual audit. A check that finds no defect belongs in your audit; do not invent a bug to fill a request.

### AUDIT-XX Short description

- Author:
- Status: open
- App version or commit checked:
- Feature or number and its intended behavior or definition:
- Inputs and steps to reproduce:
- Expected result:
- Actual result:
- Evidence (including file, function, and relevant lines if code was checked):
- Likely cause, if established, and remaining uncertainty:
- Requested change:
- Verification check and expected result:
- Implementation commit and verification result, if resolved:

Record findings without undoing a teammate's work. Mark a request resolved only after verifying the change.

### CR-001 Specialty analysis is blocked by map error

- Author: Angana Shah
- Status: open
- App version or commit checked: 6d871d5
- Feature or number and its intended behavior or definition: The provider specialty filter should update the dashboard and allow the user to view the specialty-filtered map and analysis.
- Inputs and steps to reproduce: Start the app, leave County set to All counties, and select Allergy under Provider specialty.
- Expected result: The Allergy-filtered dashboard, map, and analysis render without an error.
- Actual result: The statewide median changes from 223.71 to 0.20, but the app crashes with AttributeError: module 'plotly.express' has no attribute 'scatter_mapbox'.
- Evidence: app.py line 85 calls px.scatter_mapbox() inside make_rate_map().
- Likely cause, if established, and remaining uncertainty: The installed Plotly version does not support px.scatter_mapbox. The exact replacement method still needs to be confirmed.
- Requested change: Update the map code to use a Plotly method supported by the installed version.
- Verification check and expected result: Start the app and confirm that both All specialties and Allergy render the map and remaining dashboard sections without an error.
- Implementation commit and verification result, if resolved: Not yet resolved.
