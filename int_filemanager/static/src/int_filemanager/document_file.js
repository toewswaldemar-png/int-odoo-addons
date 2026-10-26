import { FileModelMixin } from "@web/core/file_viewer/file_model";
import { imageUrl, url } from "@web/core/utils/urls";

export const MODEL = "int.filemanager.document";
// Binary fields of the content route: the upload, and the PDF made by the text recognition or
// the preview of an office file.
const CONTENT_FIELD = "content";
const VIEWER_PDF_FIELD = "viewer_pdf_content";
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
// The old office formats: their text is read from the PDF of the preview, page by page.
const PAGED_MIMETYPES = [
    "application/msword",
    "application/rtf",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
];
// A text file is read whole into the viewer.
export const TEXT_MAX_SIZE = 2 * 1024 * 1024;

function contentRoute(id, field) {
    return `/web/content/${MODEL}/${id}/${field}`;
}

/** A document as the core's file viewer wants a file. */
export class DocumentFile extends FileModelMixin(Object) {
    /** @param {Object} values the fields of a document; `hit`: the place a text search found */
    constructor(values) {
        super();
        Object.assign(this, values);
    }

    /** The recognized PDF or the preview if there is one, else the file. */
    get urlRoute() {
        return contentRoute(this.id, this.viewer_pdf_checksum ? VIEWER_PDF_FIELD : CONTENT_FIELD);
    }

    /** @override */
    get urlQueryParams() {
        const params = { ...super.urlQueryParams };
        if (this.viewer_pdf_checksum) {
            params.unique = this.viewer_pdf_checksum;
        }
        return params;
    }

    /** @override An office file with a preview is shown as a PDF. */
    get isPdf() {
        return Boolean(super.isPdf || this.viewer_pdf_checksum);
    }

    /** Whether the pages of the text are the pages of the PDF shown: not the blocks of an office file. */
    get hasTextPages() {
        return Boolean(super.isPdf || PAGED_MIMETYPES.includes(this.mimetype));
    }

    /** @override The download is never the recognized PDF. */
    get downloadUrl() {
        return url(contentRoute(this.id, CONTENT_FIELD), {
            ...super.urlQueryParams,
            download: true,
        });
    }

    /** @override The hash `search` starts too early: `DocumentFileViewer` marks the words. */
    get defaultSource() {
        const source = super.defaultSource;
        if (!this.hasTextPages || !this.hit) {
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

/** @param {Object} [hit] the place the file shows, default: the first of the `content_hits` */
export function documentFileFromRecord(record, hit) {
    const { name, mimetype, checksum, size, viewer_pdf_checksum, content_hits, folder_id } = record.data;
    return new DocumentFile({
        id: record.resId,
        name,
        mimetype,
        checksum,
        size,
        viewer_pdf_checksum,
        hit: hit || content_hits?.hits?.[0],
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
    return imageUrl(MODEL, file.id, field, { width: size, height: size, unique: file.checksum });
}

export async function readDocumentFile(orm, id) {
    const [values] = await orm.read(
        MODEL,
        [id],
        ["name", "mimetype", "checksum", "size", "viewer_pdf_checksum"]
    );
    return new DocumentFile(values);
}

export function documentFilesFromRecords(records, record, hit) {
    const inPage = records.includes(record) ? records : [record];
    const files = inPage.map((each) =>
        documentFileFromRecord(each, each === record ? hit : undefined)
    );
    return { file: files[inPage.indexOf(record)], files };
}
