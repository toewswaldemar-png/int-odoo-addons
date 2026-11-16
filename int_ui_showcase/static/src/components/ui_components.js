import { Component } from "@odoo/owl";
import { Notebook } from "@web/core/notebook/notebook";
import { registry } from "@web/core/registry";
import {
    BootstrapPage,
    DashboardPage,
    DialogsPage,
    InputsPage,
    MenusPage,
    NativeNumpadPage,
    NumpadPage,
    OdooPage,
    SelectorsPage,
    ViewsPage,
} from "./ui_pages";

export class UiComponents extends Component {
    static template = "int_ui_showcase.UiComponents";
    static components = {
        BootstrapPage,
        DashboardPage,
        DialogsPage,
        InputsPage,
        MenusPage,
        NativeNumpadPage,
        Notebook,
        NumpadPage,
        OdooPage,
        SelectorsPage,
        ViewsPage,
    };
    static props = ["*"];
}

registry.category("actions").add("int_ui_showcase.ui_components", UiComponents);
