import { FileModelMixin } from "@web/core/file_viewer/file_model";
import { imageUrl, url } from "@web/core/utils/urls";

export const MODEL = "int.filemanager.document";
// The binary fields that the content route serves: the file as it was uploaded, and the PDF that
// the text recognition made of a scan (it has a text layer that the PDF viewer can search).
const CONTENT_FIELD = "content";
const OCR_FIELD = "ocr_content";
// The first page of a PDF as a small picture: a field of the core's own image type.
const THUMBNAIL_FIELD = "thumbnail";
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
 * Where the addresses of the files come from. The user's web client serves them from the routes
 * of the core; the page of the guests of a share replaces these functions (`guest_addresses.js`)
 * with ones that build the addresses of the share, which carry its token. Nothing else in the
 * components knows the difference.
 */
export const addresses = {
    /** @returns {string} the route that serves a binary field of a document */
    content: (id, field) => `/web/content/${MODEL}/${id}/${field}`,
    /** @returns {string|false} the address of a smaller version of a picture of a document */
    image: (id, field, params) => imageUrl(MODEL, id, field, params),
    /** @returns {Object} query parameters that every address of a file carries */
    params: () => ({}),
};

function contentRoute(id, field) {
    return addresses.content(id, field);
}

/**
 * A document as the core's file viewer wants a file. The core's model builds the addresses
 * of attachments; a document's bytes lie in a blob, served by the content route of the
 * document (the html editor does the same for its files: `StateFileModel`).
 */
export class DocumentFile extends FileModelMixin(Object) {
    /**
     * @param {{id: number, name: string, mimetype: string, checksum: string, size: number,
     *      ocr_checksum?: string|false, hit?: {page: number, terms: string[]}}} values
     *      `hit` is the place in the file that a full text search found: a PDF opens on its
     *      page and the viewer marks the words. `ocr_checksum` is the checksum of the PDF that
     *      the text recognition made of a scan: the viewer shows that one (it can be searched),
     *      the download is the original
     */
    constructor(values) {
        super();
        Object.assign(this, values);
    }

    /** The recognized PDF if there is one, else the file. */
    get urlRoute() {
        return contentRoute(this.id, this.isPdf && this.ocr_checksum ? OCR_FIELD : CONTENT_FIELD);
    }

    /** @override The browser keeps a file for good: its checksum changes with the content. */
    get urlQueryParams() {
        const params = { ...super.urlQueryParams, ...addresses.params() };
        if (this.isPdf && this.ocr_checksum) {
            params.unique = this.ocr_checksum;
        }
        return params;
    }

    /** @override The download is the file that was uploaded, never the recognized PDF. */
    get downloadUrl() {
        return url(contentRoute(this.id, CONTENT_FIELD), {
            ...super.urlQueryParams,
            ...addresses.params(),
            download: true,
        });
    }

    /**
     * @override
     * The PDF viewer takes the page from the hash of its address (`page`; `viewer.js`,
     * `setHash`). The words are marked by `DocumentFileViewer` after the load: the `search` of
     * the hash starts at the wrong time, and the viewer then puts the word at the top edge.
     */
    get defaultSource() {
        const source = super.defaultSource;
        if (!this.isPdf || !this.hit) {
            return source;
        }
        return `${source}&${new URLSearchParams({ page: this.hit.page })}`;
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
 *      checksum, ocr_checksum and size loaded (and `content_hits`, if the list was searched by the full text)
 * @param {Number} [hitIndex] which of the hits of the record the file shows
 * @returns {DocumentFile}
 */
export function documentFileFromRecord(record, hitIndex = 0) {
    const { name, mimetype, checksum, size, ocr_checksum, content_hits } = record.data;
    const hit = content_hits?.hits?.[hitIndex];
    return new DocumentFile({
        id: record.resId,
        name,
        mimetype,
        checksum,
        size,
        ocr_checksum,
        hit,
    });
}

/**
 * The address of the small picture of a record of the list or the kanban: a small version of the
 * image itself, or the first page of a PDF that the server has drawn (`thumbnail_state`).
 * `unique` lets the browser keep the picture for good: the checksum changes with the content.
 * @param {Object} record a record of the model `int.filemanager.document`, with `thumbnail_state` loaded
 * @param {Number} size the width and the height asked for, in pixels
 * @returns {string|false} `false` for a record without a picture: the symbol of the file type shows
 */
export function thumbnailUrl(record, size) {
    const file = documentFileFromRecord(record);
    if (!record.resId) {
        return false;
    }
    let field;
    if (file.isImage) {
        field = CONTENT_FIELD;
    } else if (file.isPdf && record.data.thumbnail_state === "done") {
        field = THUMBNAIL_FIELD;
    } else {
        return false;
    }
    // A guest does not get the checksum: the time of the last change tells the browser as well.
    const unique = file.checksum || String(record.data.write_date || "");
    return addresses.image(file.id, field, { width: size, height: size, unique });
}

/**
 * @param {Object} orm the orm service
 * @param {Number} id
 * @returns {Promise<DocumentFile>} the document with the values the viewers need
 */
export async function readDocumentFile(orm, id) {
    const [values] = await orm.read(
        MODEL,
        [id],
        ["name", "mimetype", "checksum", "size", "ocr_checksum"]
    );
    return new DocumentFile(values);
}

/**
 * The files a viewer goes through for a click on a record of the list or the kanban.
 * @param {Object[]} records the records of the page
 * @param {Object} record the record that was clicked; it may be missing among `records`
 * @param {Number} [hitIndex] the hit of `record` that was clicked; the other files show their
 *      first hit
 * @returns {{file: DocumentFile, files: DocumentFile[]}} `file` is one of `files`: the viewer
 *      finds the file to start with among them by identity
 */
export function documentFilesFromRecords(records, record, hitIndex = 0) {
    const inPage = records.includes(record) ? records : [record];
    const files = inPage.map((each) =>
        documentFileFromRecord(each, each === record ? hitIndex : 0)
    );
    return { file: files[inPage.indexOf(record)], files };
}
