/** @odoo-module **/

// The words of a picture to click on and the outlines of the found values, in a layer over
// the picture. The same job as the layers ViewerOverlay puts on the pages of the PDF viewer
// (which lives in a frame of its own and so cannot be an OWL component), with the same
// helpers: boxes are shares of the picture, so the layer follows every size of it.
import {Component, useExternalListener, useState} from "@odoo/owl";
import {boxStyle, outlineBox, selectWords, wordBox} from "./value_geometry.js";

export class IntFilemanagerV2ImageWords extends Component {
    static template = "int_filemanager.v2.ImageWords";
    static props = {
        // [x0, top, x1, bottom, start, end] each, as page_words sends them
        words: Array,
        // Width and height of the picture in the unit of the word boxes
        size: Array,
        // [{fieldId, name, box}]
        markers: Array,
        // The field the user works in: its outline is drawn stronger
        activeFieldId: {optional: true},
        // Words react to the mouse only while a field waits for a value
        wordMode: Boolean,
        // ``onPick({start, end})`` when words were clicked or dragged over
        onPick: Function,
    };

    setup() {
        this.state = useState({range: null});
        this.anchor = null;
        // The mouse may be let go outside the layer.
        useExternalListener(window, "pointerup", () => this.endDrag());
    }

    wordStyle(word) {
        return boxStyle(wordBox(word, this.props.size));
    }

    markerStyle(marker) {
        return boxStyle(outlineBox(marker.box, this.props.size));
    }

    isPicking(index) {
        const range = this.state.range;
        return Boolean(range) && index >= range.first && index <= range.last;
    }

    // A click is a drag from one word to the same one.
    onPointerDown(index) {
        this.anchor = index;
        this.state.range = selectWords(this.props.words, index, index);
    }

    onPointerEnter(index) {
        if (this.anchor !== null) {
            this.state.range = selectWords(this.props.words, this.anchor, index);
        }
    }

    onPointerUp(index) {
        if (this.anchor === null) {
            return;
        }
        const {start, end} = selectWords(this.props.words, this.anchor, index);
        this.endDrag();
        this.props.onPick({start, end});
    }

    endDrag() {
        this.anchor = null;
        this.state.range = null;
    }
}
