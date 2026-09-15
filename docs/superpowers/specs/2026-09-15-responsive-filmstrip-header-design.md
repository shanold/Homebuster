# Responsive Filmstrip Header Design

## Goal
Replace the accumulated fixed-coordinate header alignment patches with one responsive filmstrip grid whose real layout cells shrink with the viewport.

## Approved behavior
- Desktop/tablet filmstrip is a real CSS grid, not fixed-width repeating divider coordinates.
- Film cells share the available viewport width and shrink/grow together.
- Desktop navigation controls occupy explicit cells and are centered by the cell itself.
- House + HOMEBUSTER branding stays independently anchored at the left and is not constrained by the site content container.
- Film dividers are drawn by the actual cells, so controls cannot drift away from their cells.
- At the existing mobile breakpoint, retain the compact logo + Menu/dropdown behavior instead of shrinking desktop cells further.
- Preserve the v0.3.45 vertical mobile dropdown and existing library tab behavior.
