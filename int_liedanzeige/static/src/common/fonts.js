/** @odoo-module **/

export const FONTS = [
    { key: "segoe-ui", label: "Segoe UI", css: '"Segoe UI", sans-serif' },
    { key: "arial", label: "Arial", css: "Arial, sans-serif" },
    { key: "verdana", label: "Verdana", css: "Verdana, sans-serif" },
    { key: "trebuchet-ms", label: "Trebuchet MS", css: '"Trebuchet MS", sans-serif' },
    { key: "georgia", label: "Georgia", css: "Georgia, serif" },
    { key: "times", label: "Times New Roman", css: '"Times New Roman", serif' },
];

export function fontCss(key) {
    return (FONTS.find((font) => font.key === key) || FONTS[0]).css;
}
