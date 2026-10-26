// Stands in for `picture.js` where the component imports it: the real class and functions, but
// `loadPicture` gives the picture that a check has put at `globalThis.__loadPicture` (the real one
// fetches an attachment of the server).
import * as real from "@int_filemanager_image_editor/image_editor/picture";

export const { canvasFits, largestExportScale, Picture } = real;

export async function loadPicture() {
    return globalThis.__loadPicture();
}
