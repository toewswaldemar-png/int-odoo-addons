// The addresses of the files on the page of the guests: the routes of the share, with the key.
// A picture is asked for in one of the sizes that the server has (it answers no others).
import { url } from "@web/core/utils/urls";
import { addresses } from "../int_filemanager/document_file";
import { shareKey, shareUrl } from "./guest_share";

const IMAGE_SIZES = [64, 128, 256, 512, 1024];

addresses.params = () => {
    const key = shareKey();
    return key ? { k: key } : {};
};

addresses.content = (id) => shareUrl(`content/${id}`);

addresses.image = (id, field, { width, unique }) => {
    if (!odoo.int_filemanager_rights.can_view) {
        return false; // the right to download does not include the pictures: the symbol shows
    }
    const params = { ...addresses.params(), unique };
    if (field === "thumbnail") {
        return url(shareUrl(`thumbnail/${id}`), params);
    }
    const size = IMAGE_SIZES.find((candidate) => candidate >= width) || IMAGE_SIZES.at(-1);
    return url(shareUrl(`image/${id}/${size}`), params);
};
