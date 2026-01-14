I have identified the issue. The code responsible for rendering the clickable measurement point dots (`addPointsToMap()`) was intentionally commented out in `frontend/src/views/BigScreen.vue`. This prevents the "dots" from appearing on the dam model, making it difficult or impossible for the user to click them and view the associated data list.

To fix this, I will uncomment the call to `addPointsToMap()` so that the measurement points are rendered as entities on the 3D map again.

**Plan:**

1. Edit `frontend/src/views/BigScreen.vue`.
2. Locate line 582 (inside `updatePointsFromIFC` function).
3. Uncomment `addPointsToMap()`.
4. (Optional) Verify if `createWaterSurface` needs to be restored, but based on the user's request focusing on "measurement points", restoring the points is the priority. I will leave water surface as is.

