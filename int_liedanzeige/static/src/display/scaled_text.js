/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";

import { fitFontSize } from "../common/layout_math";

/**
 * One line of text whose font size is fitted to the screen width.
 *
 * The size is measured at a reference size of 100vw, so the line fills the share of the
 * width that the display settings ask for. A hidden reference text, when given, is
 * measured instead of the shown one: the number then has the size of a time.
 */
export class IntLiedanzeigeScaledText extends Component {
    static template = "int_liedanzeige.ScaledText";
    static props = {
        text: String,
        scale: Number,
        fontKey: String,
        maxHeightPx: { type: Number, optional: true },
        refText: { type: String, optional: true },
        onHeight: { type: Function, optional: true },
    };

    setup() {
        this.wrapRef = useRef("wrap");
        this.textRef = useRef("text");
        this.measureRef = useRef("measure");
        this.fittedFor = null;
        this.rescale = this.rescale.bind(this);
        onMounted(() => {
            this.rescale();
            browser.addEventListener("resize", this.rescale);
            // Fonts that are not cached yet change the width once they are loaded.
            document.fonts.ready.then(this.rescale);
            document.fonts.addEventListener("loadingdone", this.rescale);
        });
        onPatched(() => {
            if (this.fittedFor !== this.fitKey()) {
                this.rescale();
            }
        });
        onWillUnmount(() => {
            browser.removeEventListener("resize", this.rescale);
            document.fonts.removeEventListener("loadingdone", this.rescale);
        });
    }

    fitKey() {
        const { scale, fontKey, maxHeightPx } = this.props;
        return `${scale}|${fontKey}|${maxHeightPx}`;
    }

    rescale() {
        const wrap = this.wrapRef.el;
        const text = this.textRef.el;
        if (!wrap || !text) {
            return;
        }
        const probe = this.measureRef.el || text;
        probe.style.fontSize = "100vw";
        // Reading the width forces the layout with the reference size.
        void probe.offsetWidth;
        const ref100 = parseFloat(getComputedStyle(probe).fontSize);
        const size = fitFontSize(
            ref100,
            wrap.offsetWidth,
            probe.scrollWidth,
            this.props.scale,
            this.props.maxHeightPx
        );
        if (size === null) {
            return;
        }
        text.style.fontSize = `${size}px`;
        probe.style.fontSize = `${size}px`;
        wrap.style.height = `${size}px`;
        this.fittedFor = this.fitKey();
        if (this.props.onHeight) {
            this.props.onHeight(size);
        }
    }
}
