/** @odoo-module **/

/**
 * Return the font size in pixels that makes a text fill a share of the available width.
 *
 * @param {number} ref100 pixel value of the reference font size (100vw)
 * @param {number} available width of the container in pixels
 * @param {number} natural width of the text at the reference font size
 * @param {number} scale share of the width the text may fill, 0 to 100
 * @param {number} [maxHeightPx] upper limit for the size
 * @returns {number | null} null when nothing can be measured yet
 */
export function fitFontSize(ref100, available, natural, scale, maxHeightPx) {
    if (natural <= 0 || available <= 0) {
        return null;
    }
    const widthScaled = Math.floor((((ref100 * available) / natural) * scale) / 100);
    return maxHeightPx === undefined ? widthScaled : Math.min(widthScaled, maxHeightPx);
}

/**
 * Return the height each line may take.
 *
 * In clock mode the time and the date share the screen half and half; in number mode the
 * number and the small clock share it in proportion to their sizes.
 */
export function heightBudget(viewportH, timeSize, subClockSize) {
    const total = timeSize + subClockSize;
    const half = Math.floor(viewportH / 2);
    return {
        clockMode: half,
        number: total > 0 ? Math.floor((viewportH * timeSize) / total) : half,
        subClock: total > 0 ? Math.floor((viewportH * subClockSize) / total) : half,
    };
}

/**
 * Return the gap between the two lines in pixels, a share of the height left over.
 *
 * @returns {number | null} null while a height is still unknown
 */
export function gapPixels(viewportH, firstHeight, secondHeight, percent) {
    if (firstHeight <= 0 || secondHeight <= 0) {
        return null;
    }
    const remaining = Math.max(0, viewportH - firstHeight - secondHeight);
    return Math.floor((remaining * percent) / 100);
}

export function pad2(value) {
    return String(value).padStart(2, "0");
}

export function formatTime(date) {
    return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

export function formatDate(date) {
    return `${pad2(date.getDate())}.${pad2(date.getMonth() + 1)}.${date.getFullYear()}`;
}
