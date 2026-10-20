// What the editor draws over the picture but never into the file: the grid, the guides of the
// snapping, the shade outside the crop and the line of a polygon that is being made. All is drawn
// in the space of the scene (the context is given the view of the canvas first).

/**
 * @param {CanvasRenderingContext2D} ctx the context of the canvas, after the marks were drawn
 * @param {number[]} view the viewport transform
 * @param {Object} parts what to draw
 * @param {{left: number, top: number, width: number, height: number}} parts.region
 * @param {number} parts.zoom
 * @param {{step: number}|null} parts.grid
 * @param {{x?: number, y?: number}[]} parts.guides
 * @param {{left: number, top: number, width: number, height: number}|null} parts.shade the part
 *      that stays light (the crop that is being chosen)
 * @param {{points: {x: number, y: number}[], color: string, width: number, closed: boolean}|null} parts.poly
 */
export function drawOverlay(ctx, view, { region, zoom, grid, guides, shade, poly }) {
    ctx.save();
    ctx.transform(...view);
    drawFrame(ctx, region, zoom);
    if (shade) {
        drawShade(ctx, region, shade);
    }
    if (grid) {
        drawGrid(ctx, region, grid.step, zoom);
    }
    for (const guide of guides) {
        drawGuide(ctx, region, guide, zoom);
    }
    if (poly) {
        drawPoly(ctx, poly, zoom);
    }
    ctx.restore();
}

// A hairline around the part that is shown, so that a picture that has the colour of the ground
// still has an edge.
function drawFrame(ctx, { left, top, width, height }, zoom) {
    ctx.lineWidth = 1 / zoom;
    ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
    ctx.strokeRect(left, top, width, height);
}

function drawShade(ctx, region, keep) {
    ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
    const { left, top, width, height } = region;
    // Four bars around the part that stays light.
    ctx.fillRect(left, top, width, keep.top - top);
    ctx.fillRect(left, keep.top + keep.height, width, top + height - keep.top - keep.height);
    ctx.fillRect(left, keep.top, keep.left - left, keep.height);
    ctx.fillRect(keep.left + keep.width, keep.top, left + width - keep.left - keep.width, keep.height);
}

function drawGrid(ctx, region, step, zoom) {
    // Below a few pixels on the screen the lines only make a haze.
    if (step * zoom < 6) {
        return;
    }
    ctx.lineWidth = 1 / zoom;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
    ctx.beginPath();
    const right = region.left + region.width;
    const bottom = region.top + region.height;
    for (let x = Math.ceil(region.left / step) * step; x <= right; x += step) {
        ctx.moveTo(x, region.top);
        ctx.lineTo(x, bottom);
    }
    for (let y = Math.ceil(region.top / step) * step; y <= bottom; y += step) {
        ctx.moveTo(region.left, y);
        ctx.lineTo(right, y);
    }
    ctx.stroke();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
    ctx.lineDashOffset = 0;
    ctx.stroke();
}

function drawGuide(ctx, region, guide, zoom) {
    ctx.lineWidth = 1 / zoom;
    ctx.strokeStyle = "#ff2d95";
    ctx.beginPath();
    if (guide.x !== undefined) {
        ctx.moveTo(guide.x, region.top);
        ctx.lineTo(guide.x, region.top + region.height);
    } else {
        ctx.moveTo(region.left, guide.y);
        ctx.lineTo(region.left + region.width, guide.y);
    }
    ctx.stroke();
}

function drawPoly(ctx, { points, color, width, closed }, zoom) {
    if (!points.length) {
        return;
    }
    ctx.lineWidth = Math.max(width, 1 / zoom);
    ctx.strokeStyle = color;
    ctx.lineJoin = "round";
    ctx.setLineDash([6 / zoom, 4 / zoom]);
    ctx.beginPath();
    points.forEach(({ x, y }, index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    if (closed) {
        ctx.closePath();
    }
    ctx.stroke();
    ctx.setLineDash([]);
    // The points of the polygon, and the first one larger: a click on it closes the shape.
    ctx.fillStyle = "#fff";
    ctx.strokeStyle = color;
    ctx.lineWidth = 1 / zoom;
    points.forEach(({ x, y }, index) => {
        ctx.beginPath();
        ctx.arc(x, y, (index ? 4 : 7) / zoom, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    });
}
