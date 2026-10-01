/** @odoo-module **/

// The values found in a file, inside the properties form of the file. The rows are Odoo's own
// form fields (label left, input right), built at runtime from what suggest_field_values
// answered, the way Odoo builds the access rights fields of a user. Edits are written to
// the JSON field of the node in the shape apply_field_values takes, so the form's own
// Save button stores them.
import {Component, onWillUpdateProps, useChildSubEnv, useState} from "@odoo/owl";
import {AutoComplete} from "@web/core/autocomplete/autocomplete";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useBus, useChildRef} from "@web/core/utils/hooks";
import {parseXML} from "@web/core/utils/xml";
import {Record} from "@web/model/record";
import {useInputField} from "@web/views/fields/input_field_hook";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {FormArchParser} from "@web/views/form/form_arch_parser";
import {FormRenderer} from "@web/views/form/form_renderer";
import {canPreview, viewerFileOf} from "../controller_mutations.js";
import {
  chooseSuggestion,
  initialRows,
  pickSelection,
  rowMarkers,
  typeText,
  valuesToSave,
} from "../value_review/value_review_edits.js";
import {EVENTS} from "./events.js";

const MAX_OPTIONS = 12;
const ADD_FIELD = "v_add";

const fieldName = (row) => `v_${row.fieldId}`;

/**
 * One value: Odoo's own autocomplete input, like the one of a contact. A click in it lists
 * what was found in the file for this field, and the values of its kind that no field took;
 * typing narrows the list, and a text of its own stays as typed.
 */
export class IntFilemanagerV2ValueInput extends Component {
  static template = "int_filemanager.v2.ValueInput";
  static components = {AutoComplete};
  static props = {...standardFieldProps, "*": true};

  setup() {
    this.inputRef = useChildRef();
    useInputField({
      getValue: () => this.value,
      ref: this.inputRef,
    });
  }

  get values() {
    return this.env.intFilemanagerValues;
  }

  get row() {
    return this.values.rowFor(this.props.name);
  }

  get value() {
    return this.props.record.data[this.props.name] || "";
  }

  get sources() {
    return [{options: (request) => this.options(request)}];
  }

  options(request) {
    const row = this.row;
    if (!row) {
      return [];
    }
    const query = request.trim().toLowerCase();
    const seen = new Set();
    const options = [];
    const add = (text, choose) => {
      if (text && !seen.has(text) && text.toLowerCase().includes(query)) {
        seen.add(text);
        options.push({label: text, onSelect: choose});
      }
    };
    for (const suggestion of row.suggestions) {
      add(suggestion.source_text, () =>
        this.choose(() => chooseSuggestion(row, suggestion), suggestion.source_text)
      );
    }
    for (const value of this.values.unassignedOf(row.valueType)) {
      add(value.value_text, () =>
        this.choose(
          () => pickSelection(row, {source_text: value.value_text, start: value.start}),
          value.value_text
        )
      );
    }
    const shown = options.slice(0, MAX_OPTIONS);
    // The last entry, like "Search more..." of a contact: the value is in the document.
    if (this.values.canPick()) {
      shown.push({
        label: _t("Select in the document..."),
        cssClass: "o_int_filemanager_pick_option",
        onSelect: () => this.values.startPick(this.props.name),
      });
    }
    return shown;
  }

  /** The preview marks the place of the value of the field the user works in. */
  onFocus() {
    if (this.row) {
      this.values.activate(this.row.fieldId);
    }
  }

  /** The row and the input change together. */
  choose(change, text) {
    change();
    return this.props.record.update({[this.props.name]: text});
  }
}

export const intFilemanagerV2ValueInput = {
  component: IntFilemanagerV2ValueInput,
  supportedTypes: ["char"],
};

registry
  .category("fields")
  .add("int_filemanager_v2_value_input", intFilemanagerV2ValueInput);

/**
 * The last row of the form: an input that lists the fields of the catalogue without a row
 * and adds the chosen one, the way the tags of a record are added.
 */
export class IntFilemanagerV2AddField extends Component {
  static template = "int_filemanager.v2.AddField";
  static components = {AutoComplete};
  static props = {...standardFieldProps, "*": true};

  get placeholder() {
    return _t("Search a field...");
  }

  get sources() {
    return [{options: (request) => this.options(request)}];
  }

  options(request) {
    const values = this.env.intFilemanagerValues;
    const query = request.trim().toLowerCase();
    return values
      .addable()
      .filter((choice) => choice.label.toLowerCase().includes(query))
      .map((choice) => ({
        label: choice.label,
        onSelect: () => values.add(choice.value),
      }));
  }
}

registry.category("fields").add("int_filemanager_v2_add_field", {
  component: IntFilemanagerV2AddField,
  supportedTypes: ["char"],
});

export class IntFilemanagerV2ValuesField extends Component {
  static template = "int_filemanager.v2.ValuesField";
  static components = {Record, FormRenderer};
  static props = {...standardFieldProps};

  setup() {
    this.state = useState({rev: 0});
    this.rows = [];
    this.visibleRows = [];
    this.payload = null;
    this.load(this.props.record.data[this.props.name]);
    useChildSubEnv({
      intFilemanagerValues: {
        rowFor: (name) => this.rowByName[name],
        addable: () => this.addable,
        add: (fieldId) => this.onAddField(fieldId),
        canPick: () => this.canPick,
        startPick: (name) => this.startPick(name),
        activate: (fieldId) => this.bus.trigger(EVENTS.ACTIVE, {fieldId}),
        unassignedOf: (valueType) =>
          ((this.payload && this.payload.unassigned) || []).filter(
            (value) => value.value_type === valueType
          ),
      },
    });
    onWillUpdateProps((next) => {
      const payload = next.record.data[next.name];
      // Our own edits carry "edits"; anything without them came from the server, e.g. after
      // saving, and starts the rows again.
      if (payload && !("edits" in payload) && payload !== this.payload) {
        this.load(payload);
        this.state.rev++;
      }
    });
    this.hooks = {onRecordChanged: this.onRecordChanged.bind(this)};
    useBus(this.bus, EVENTS.PICKED, (ev) => this.onPicked(ev.detail));
    useBus(this.bus, EVENTS.PREVIEW_READY, () => this.pushMarkers());
  }

  /** The bus the preview of the same form listens on. */
  get bus() {
    return this.props.record.model.bus;
  }

  load(payload) {
    this.payload = payload || null;
    this.rows =
      payload && payload.state === "ready"
        ? initialRows(payload.fields, {all: true})
        : [];
    this.rowByName = Object.fromEntries(this.rows.map((row) => [fieldName(row), row]));
    this.buildView();
    this.pushMarkers();
  }

  /**
   * The form of the rows to show: those with a value and those the user added. The other
   * fields of the catalogue are offered by the "Add field" menu.
   */
  buildView() {
    this.visibleRows = this.rows.filter((row) => row.text || row.added);
    this.fields = {};
    this.values = {};
    for (const row of this.visibleRows) {
      this.fields[fieldName(row)] = {string: row.name, type: "char"};
      this.values[fieldName(row)] = row.text;
    }
    const inputs = this.visibleRows.map(
      (row) =>
        `<field name="${fieldName(row)}" widget="int_filemanager_v2_value_input"/>`
    );
    if (this.addable.length) {
      this.fields[ADD_FIELD] = {string: _t("Add field"), type: "char"};
      this.values[ADD_FIELD] = "";
      inputs.push(`<field name="${ADD_FIELD}" widget="int_filemanager_v2_add_field"/>`);
    }
    const arch = `<t><group>${inputs.join("")}</group></t>`;
    this.archInfo = new FormArchParser().parse(
      parseXML(arch),
      {main: {fields: this.fields}},
      "main"
    );
  }

  /** The fields of the catalogue that have no row yet, for the "Add field" menu. */
  get addable() {
    return this.rows
      .filter((row) => !this.visibleRows.includes(row))
      .map((row) => ({value: row.fieldId, label: row.name}));
  }

  onAddField(fieldId) {
    const row = this.rows.find((r) => r.fieldId === fieldId);
    if (row) {
      row.added = true;
      this.buildView();
      this.state.rev++;
    }
  }

  get status() {
    return this.payload ? this.payload.state : false;
  }

  get hasRows() {
    return this.visibleRows.length > 0;
  }

  get hasForm() {
    return this.hasRows || this.addable.length > 0;
  }

  get hasUnconfirmed() {
    return this.visibleRows.some((row) => row.text && !row.confirmed);
  }

  get warnings() {
    return (this.payload && this.payload.warnings) || [];
  }

  get partner() {
    const partner = this.payload && this.payload.partner;
    const current = this.props.record.data.partner_id;
    return partner && (!current || current.id !== partner.id) ? partner : false;
  }

  onUsePartner() {
    const partner = this.partner;
    this.props.record.update({
      partner_id: {id: partner.id, display_name: partner.name},
    });
  }

  onAcceptAll() {
    this.commit();
  }

  onRecordChanged(_record, changes) {
    for (const [name, value] of Object.entries(changes)) {
      const row = this.rowByName[name];
      if (row && name !== ADD_FIELD) {
        if ((value || "") !== row.text) {
          typeText(row, value || "");
        }
        this.values[name] = value;
      }
    }
    this.commit();
  }

  /** Whether the document can be asked for a value: a PDF whose words are known. */
  get canPick() {
    return Boolean(
      this.status === "ready" &&
        canPreview(this.props.record) &&
        viewerFileOf(this.props.record).isPdf
    );
  }

  startPick(name) {
    const row = this.rowByName[name];
    if (row) {
      this.bus.trigger(EVENTS.PICK, {fieldId: row.fieldId, name: row.name});
    }
  }

  /** Words of the document were chosen for a field: its row takes them as typed. */
  onPicked({fieldId, suggestion}) {
    const row = this.rows.find((r) => r.fieldId === fieldId);
    if (!row) {
      return;
    }
    pickSelection(row, suggestion);
    this.values[fieldName(row)] = row.text;
    this.state.rev++;
    this.commit();
  }

  /** The outlines of the values read from the document, for the preview to draw. */
  pushMarkers() {
    const sizes = (this.payload && this.payload.page_sizes) || {};
    this.bus.trigger(EVENTS.MARKERS, {markers: rowMarkers(this.rows, sizes)});
  }

  /** The edits go to the form record; the form's Save stores them. */
  commit() {
    this.pushMarkers();
    this.props.record.update({
      [this.props.name]: {
        ...this.payload,
        edits: valuesToSave(this.rows),
      },
    });
  }
}

export const intFilemanagerV2ValuesField = {
  component: IntFilemanagerV2ValuesField,
  supportedTypes: ["json"],
  additionalClasses: ["w-100"],
  displayName: _t("Values found in the file"),
};

registry
  .category("fields")
  .add("int_filemanager_v2_values", intFilemanagerV2ValuesField);
