import { FileModelMixin } from "@web/core/file_viewer/file_model";
import { imageUrl, url } from "@web/core/utils/urls";

export const MODEL = "int.filemanager.document";
// Binary fields of the content route: the upload, and the PDF made by the text recognition.
const CONTENT_FIELD = "content";
const OCR_FIELD = "ocr_content";
const THUMBNAIL_FIELD = "thumbnail";
// The core's list without svg (stored as text here), tiff and ico (not shown by a browser).
const IMAGE_MIMETYPES = ["image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp"];
// The core's audio/video list plus what it lacks.
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
// A text file is read whole into the viewer.
export const TEXT_MAX_SIZE = 2 * 1024 * 1024;

/** The routes of the core; the guest page replaces them with those of the share. */
export const addresses = {
    content: (id, field) => `/web/content/${MODEL}/${id}/${field}`,
    /** @returns {string|false} the address of a smaller version of a picture of a document */
    image: (id, field, params) => imageUrl(MODEL, id, field, params),
    params: () => ({}),
};

function contentRoute(id, field) {
    return addresses.content(id, field);
}

/** A document as the core's file viewer wants a file. */
export class DocumentFile extends FileModelMixin(Object) {
    /** @param {Object} values the fields of a document; `hit`: the place a text search found */
    constructor(values) {
        super();
        Object.assign(this, values);
    }

    /** The recognized PDF if there is one, else the file. */
    get urlRoute() {
        return contentRoute(this.id, this.isPdf && this.ocr_checksum ? OCR_FIELD : CONTENT_FIELD);
    }

    /** @override */
    get urlQueryParams() {
        const params = { ...super.urlQueryParams, ...addresses.params() };
        if (this.isPdf && this.ocr_checksum) {
            params.unique = this.ocr_checksum;
        }
        return params;
    }

    /** @override The download is never the recognized PDF. */
    get downloadUrl() {
        return url(contentRoute(this.id, CONTENT_FIELD), {
            ...super.urlQueryParams,
            ...addresses.params(),
            download: true,
        });
    }

    /** @override The hash `search` starts too early: `DocumentFileViewer` marks the words. */
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

    /** A picture the editor can store anew: not a GIF (it would lose its frames). */
    get isEditable() {
        return this.isImage && this.mimetype !== "image/gif" && Boolean(this.folder_id);
    }

    get isText() {
        return super.isText && !(this.size > TEXT_MAX_SIZE);
    }

    get isVideo() {
        return super.isVideo || MEDIA_MIMETYPES.includes(this.mimetype);
    }
}

/** @param {Number} [hitIndex] which of the `content_hits` of the record the file shows */
export function documentFileFromRecord(record, hitIndex = 0) {
    const { name, mimetype, checksum, size, ocr_checksum, content_hits, folder_id } = record.data;
    const hit = content_hits?.hits?.[hitIndex];
    return new DocumentFile({
        id: record.resId,
        name,
        mimetype,
        checksum,
        size,
        ocr_checksum,
        hit,
        folder_id: folder_id?.id,
    });
}

/** The address of the small picture of a record; `false` shows the symbol of the file type. */
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
    // A guest gets no checksum: the time of the last change serves as well.
    const unique = file.checksum || String(record.data.write_date || "");
    return addresses.image(file.id, field, { width: size, height: size, unique });
}

export async function readDocumentFile(orm, id) {
    const [values] = await orm.read(
        MODEL,
        [id],
        ["name", "mimetype", "checksum", "size", "ocr_checksum"]
    );
    return new DocumentFile(values);
}

export function documentFilesFromRecords(records, record, hitIndex = 0) {
    const inPage = records.includes(record) ? records : [record];
    const files = inPage.map((each) =>
        documentFileFromRecord(each, each === record ? hitIndex : 0)
    );
    return { file: files[inPage.indexOf(record)], files };
}
