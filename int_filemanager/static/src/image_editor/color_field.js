import { Component } from "@odoo/owl";
import { DEFAULT_COLORS } from "@web/core/color_picker/color_picker";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";

/**
 * A colour: a swatch that opens the palette of the core's colour picker, and a field for any
 * other colour (the colour chooser of the browser).
 */
export class ColorField extends Component {
    static template = "int_filemanager.ImageEditorColorField";
    static components = { Dropdown };
    static props = {
        value: String,
        onChange: Function,
        title: { type: String, optional: true },
    };

    setup() {
        this.palette = DEFAULT_COLORS;
        this.menu = useDropdownState();
    }

    isChosen(color) {
        return color.toLowerCase() === this.props.value.toLowerCase();
    }

    choose(color) {
        this.menu.close();
        this.props.onChange(color);
    }

    onCustomColor(ev) {
        this.props.onChange(ev.target.value.toUpperCase());
    }
}
