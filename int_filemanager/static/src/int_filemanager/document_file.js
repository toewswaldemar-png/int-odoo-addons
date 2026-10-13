import { FileModelMixin } from "@web/core/file_viewer/file_model";

export const MODEL = "int.filemanager.document";
// What the browser shows in an <img>; the core's list adds svg, tiff and ico, which a document
// never has (svg is stored as text) or a browser does not show.
const IMAGE_MIMETYPES = ["image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp"];
// Played by the browser's own player, like the core's audio/video list, plus what it lacks.
const MEDIA_MIMETYPES = [
    "audio/aac",
    "audio/flac",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/x-flac",
    "audio/x-wav",
    "video/ogg",
];
// A text file is read whole into the viewer: above this size it is offered as a download.
export const TEXT_MAX_SIZE = 2 * 1024 * 1024;

/**
 * A document as the core's file viewer wants a file. The core's model builds the addresses
 * of attachments; a document's bytes lie in a blob, served by the content route of the
 * document (the html editor does the same for its files: `StateFileModel`).
 */
export class DocumentFile extends FileModelMixin(Object) {
    /**
     * @param {{id: number, name: string, mimetype: string, checksum: string, size: number}} values
     */
    constructor(values) {
        super();
        Object.assign(this, values);
    }

    get urlRoute() {
        return `/web/content/${MODEL}/${this.id}/content`;
    }

    get isImage() {
        return IMAGE_MIMETYPES.includes(this.mimetype);
    }

    get isText() {
        return super.isText && !(this.size > TEXT_MAX_SIZE);
    }

    get isVideo() {
        return super.isVideo || MEDIA_MIMETYPES.includes(this.mimetype);
    }
}

/**
 * @param {Object} record a record of the model `int.filemanager.document` with name, mimetype,
 *      checksum and size loaded
 * @returns {DocumentFile}
 */
export function documentFileFromRecord(record) {
    const { name, mimetype, checksum, size } = record.data;
    return new DocumentFile({ id: record.resId, name, mimetype, checksum, size });
}

/**
 * @param {Object} orm the orm service
 * @param {Number} id
 * @returns {Promise<DocumentFile>} the document with the values the viewers need
 */
export async function readDocumentFile(orm, id) {
    const [values] = await orm.read(MODEL, [id], ["name", "mimetype", "checksum", "size"]);
    return new DocumentFile(values);
}

/**
 * The files a viewer goes through for a click on a record of the list or the kanban.
 * @param {Object[]} records the records of the page
 * @param {Object} record the record that was clicked; it may be missing among `records`
 * @returns {{file: DocumentFile, files: DocumentFile[]}} `file` is one of `files`: the viewer
 *      finds the file to start with among them by identity
 */
export function documentFilesFromRecords(records, record) {
    const inPage = records.includes(record) ? records : [record];
    const files = inPage.map(documentFileFromRecord);
    return { file: files[inPage.indexOf(record)], files };
}
