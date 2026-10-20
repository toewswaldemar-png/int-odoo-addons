// Where a mark that is dragged wants to stop: on the lines of the grid, or on the edges and the
// middles of the other marks and of the picture. Plain numbers in, a shift and the guide lines out.
import { nearest, snapTo } from "./geometry";

/** @returns {number[]} the three lines of a box on one axis: start, middle, end */
function linesOf(start, length) {
    return [start, start + length / 2, start + length];
}

/**
 * @param {{left: number, top: number, width: number, height: number}} box the mark that moves
 * @param {Object} options
 * @param {{left: number, top: number, width: number, height: number}[]} options.others
 * @param {{left: number, top: number, width: number, height: number}} options.region
 * @param {number} options.distance how near a line has to be, in units of the scene
 * @param {number|null} options.grid the step of the grid if marks snap to it
 * @param {boolean} options.objects whether marks snap to the other marks and the picture
 * @returns {{dx: number, dy: number, guides: {x?: number, y?: number}[]}}
 */
export function snapMove(box, { others, region, distance, grid, objects }) {
    const guides = [];
    const axes = [
        { key: "x", start: box.left, length: box.width, region: [region.left, region.width], boxes: (b) => linesOf(b.left, b.width) },
        { key: "y", start: box.top, length: box.height, region: [region.top, region.height], boxes: (b) => linesOf(b.top, b.height) },
    ];
    const shift = { x: 0, y: 0 };
    for (const axis of axes) {
        const mine = linesOf(axis.start, axis.length);
        if (grid) {
            // The start of the mark goes to the nearest line of the grid.
            const to = snapTo(mine[0], grid);
            if (Math.abs(to - mine[0]) <= distance) {
                shift[axis.key] = to - mine[0];
            }
            continue;
        }
        if (!objects) {
            continue;
        }
        const targets = [...linesOf(...axis.region), ...others.flatMap((other) => axis.boxes(other))];
        let best = null;
        for (const line of mine) {
            const target = nearest(line, targets, distance);
            if (target !== null && (best === null || Math.abs(target - line) < Math.abs(best.target - best.line))) {
                best = { line, target };
            }
        }
        if (best) {
            shift[axis.key] = best.target - best.line;
            guides.push(axis.key === "x" ? { x: best.target } : { y: best.target });
        }
    }
    return { dx: shift.x, dy: shift.y, guides };
}
