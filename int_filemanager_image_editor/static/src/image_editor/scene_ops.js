// Turning and flipping the whole scene: the picture and every mark go with it, so that the marks
// stay where they were on the picture. The crop turns too.
import { flipPoint, flipRect, turnPoint, turnRect } from "./geometry";
import { isText } from "./marks";

const { Point } = window.fabric;

function moveCenter(object, point) {
    object.setPositionByOrigin(new Point(point.x, point.y), "center", "center");
    object.setCoords();
}

function normalized(angle) {
    return ((angle % 360) + 360) % 360;
}

/**
 * A quarter turn clockwise.
 * @returns {Object|null} the crop after the turn
 */
export function turnScene(canvas, picture, crop) {
    const size = picture.sceneSize;
    for (const object of [picture.image, ...canvas.getObjects()]) {
        const center = turnPoint(object.getCenterPoint(), size);
        object.set({ angle: normalized(object.angle + 90) });
        moveCenter(object, center);
    }
    return crop ? turnRect(crop, size) : null;
}

/**
 * A mirror image across the vertical axis (`horizontal`) or the horizontal one. A text keeps its
 * letters the right way round: only its place is mirrored.
 * @returns {Object|null} the crop after the flip
 */
export function flipScene(canvas, picture, crop, horizontal) {
    const size = picture.sceneSize;
    for (const object of [picture.image, ...canvas.getObjects()]) {
        const center = flipPoint(object.getCenterPoint(), size, horizontal);
        if (!isText(object)) {
            object.set(
                horizontal
                    ? { flipX: !object.flipX, angle: normalized(-object.angle) }
                    : { flipY: !object.flipY, angle: normalized(-object.angle) }
            );
        }
        moveCenter(object, center);
    }
    return crop ? flipRect(crop, size, horizontal) : null;
}
