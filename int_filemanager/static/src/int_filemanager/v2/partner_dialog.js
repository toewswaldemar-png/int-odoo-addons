/** @odoo-module **/

import {Component} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {Record} from "@web/model/record";
import {Field} from "@web/views/fields/field";

// Link a file or folder to a contact (partner_id).
export class IntFilemanagerV2PartnerDialog extends Component {
  static template = "int_filemanager.v2.PartnerDialog";
  static components = {Dialog, Record, Field};
  static props = {
    nodeId: Number,
    close: Function,
    onSaved: Function,
  };

  get fields() {
    return {
      partner_id: {type: "many2one", string: "Contact", relation: "res.partner"},
    };
  }

  get activeFields() {
    return {partner_id: {}};
  }

  async onSave(record) {
    await record.save({reload: false});
    this.props.onSaved();
    this.props.close();
  }

  async onClear(record) {
    record.update({partner_id: false});
    await this.onSave(record);
  }
}
