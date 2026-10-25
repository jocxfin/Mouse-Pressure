# Pressure Studio 5.0

## Curve Studio

The left and right analog buttons can have different curves.

1. Open **Pressure**, select a button, and keep **Use the same settings for both buttons** unchecked when configuring them independently.
2. Select **Custom (5-point)** from **Pressure curve**.
3. Drag the 25%, 50%, and 75% points vertically. Their input positions remain fixed so the curve cannot fold backward. The percentages below the graph also allow precise values.
4. Choose **Load shape** to start from a linear, fine-control, soft-brush, inking, or quick-build shape.
5. Set **Reach full pressure at**, then click **Apply changes**.

The curve starts at 0% and finishes at 100%. The interpolation remains monotonic, including at the knot boundaries.

**Reach full pressure at** applies to all curves, including Exponential. Its default is 95% of the calibrated pressure span, leaving room for mechanical variation near full press. Choose 100% for an uncapped range or lower it when the button cannot reliably reach the top of its calibration. Recalibrate the input range if the minimum or maximum values do not correspond to the physical button.

For Photoshop, to keep size between 70% and 100% while varying opacity or flow over the full pressure range, configure **Shape Dynamics → Minimum Diameter: 70%** and **Transfer → Opacity or Flow → Pen Pressure** in Photoshop. Mouse Pressure transmits the pressure signal; the brush preset determines how it affects those properties.

## Profiles

The **Profiles** page stores individual button curves, output targets, suppression choices, and pressure behavior. Hardware settings remain global.

- **New from current** creates a profile using the mapping currently applied.
- **Save current mapping** replaces the selected profile's saved mappings.
- **Rename**, **Delete**, **Import profile**, and **Export profile** manage the library.
- **Assigned executable names** accepts a comma-separated list such as Photoshop.exe, Krita.exe.
- **Switch profiles when their assigned application comes into focus** enables automatic matching.

The selected manual profile is the fallback for any application without an assignment. An application may be assigned to only one profile. Switching is deferred when either physical mouse button is held, during calibration, or while there are unsaved changes.

Saved profiles reside in ~/.mouse-pressure/profiles.json. The current settings remain in ~/.mouse-pressure/config.json; older config files are read and migrated automatically. Imported profiles do not take over existing application assignments.

## Stroke export

Enable **Debug mode** under Mouse settings to record stroke traces. In **Stroke Analysis**, select a trace and choose:

- **Export CSV** to preserve timestamp, screen coordinates, pressure, rotation, tilt, flags, and delivery status for each successful pen report.
- **Export SVG** to draw vector stroke geometry using recorded pressure as approximate stroke diameter. Choose the maximum diameter on export.

SVG exports reproduce the recorded trajectory and pressure levels, not a drawing application's brush texture, blending, or opacity. The background is transparent.

## Button combinations

To control Photoshop brush-tip rotation independently, set left-click output to **Pressure** and right-click output to **Rotation**. In Photoshop, set **Brush Settings → Shape Dynamics → Angle Jitter → Control: Rotation**. For tilt-responsive brushes, select **X-tilt** or **Y-tilt** and the corresponding pen-tilt control in the drawing application.
