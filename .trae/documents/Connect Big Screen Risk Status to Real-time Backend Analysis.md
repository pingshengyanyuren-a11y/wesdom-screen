I will modify `BigScreen.vue` to fetch real-time risk data from the backend and update the display status accordingly.

**Step 1: Update Frontend Logic (`frontend/src/views/BigScreen.vue`)**
- Import `detectAnomalies` API.
- Add `syncRiskStatus` function to fetch anomaly data.
- Integrate this function into the data loading process (`loadMonitoringPoints`) to ensure status is updated immediately after page load.
- Map backend severity levels to frontend status:
    - `high` -> `danger` (Red)
    - `medium` / `low` -> `warning` (Yellow)
    - Others -> `normal` (Green)

This ensures the "Standard" defined in the backend (Z-Score > 3 or AI residual high) is correctly reflected on the Big Screen without modifying the database or other components.