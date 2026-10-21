import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    makeMockEnv,
    mockService,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { Component, reactive, useRef, xml } from "@odoo/owl";
import { user } from "@web/core/user";
import { DocumentDragState } from "@int_filemanager/int_filemanager/views/drag/document_drag_state";
import {
    makeDragGhost,
    placeDragGhost,
} from "@int_filemanager/int_filemanager/views/drag/document_drag_ghost";
import { useDocumentDragSource } from "@int_filemanager/int_filemanager/views/drag/document_drag_source_hook";
import { useMoveDocuments } from "@int_filemanager/int_filemanager/views/drag/document_move";

const ROOT = { id: 10, display_name: "Root" };
const HALLO = { id: 11, display_name: "Hallo" };
const FOLDERS = {
    id: 1,
    type: "category",
    fieldName: "folder_id",
    activeValueId: ROOT.id,
    values: new Map([ROOT, HALLO].map((folder) => [folder.id, folder])),
};

/** A record of a list: `selected` is the tick of the row. */
function makeRecord(id, { selected = false, isInEdition = false } = {}) {
    return {
        id: `datapoint_${id}`,
        resId: id,
        selected,
        isInEdition,
        data: { name: `file_${id}.wav`, mimetype: "audio/x-wav" },
    };
}

/**
 * The environment of a view with the folders in the panel (`drag` is what the rows and the panel
 * share) and the services that the drag calls.
 */
async function makeEnv({ canMove = true } = {}) {
    const calls = [];
    patchWithCleanup(user, { checkAccessRight: async () => canMove });
    mockService("ui", { isSmall: false });
    mockService("orm", { write: async (...args) => calls.push(["write", ...args]) });
    mockService("action", { doAction: async (action) => calls.push(["doAction", action]) });
    mockService("notification", { add: (message) => calls.push(["notification", message]) });
    const drag = reactive(new DocumentDragState());
    await makeMockEnv({
        searchModel: { drag, getSections: (predicate) => [FOLDERS].filter(predicate) },
    });
    return { drag, calls };
}

/** Rows that can be dragged, and the folders of a panel; `records` is what the view shows. */
async function mountRows(records) {
    class Rows extends Component {
        static template = xml`
            <div>
                <div t-ref="root" class="rows">
                    <div t-foreach="records" t-as="record" t-key="record.id" class="row"
                         t-att-data-id="record.id" t-esc="record.data.name" style="height: 20px"/>
                </div>
                <div class="o_search_panel" style="width: 200px">
                    <header class="root" data-drop-folder="10" style="height: 30px">Root</header>
                    <header class="hallo" data-drop-folder="11" style="height: 30px">Hallo</header>
                </div>
            </div>`;
        static props = {};
        setup() {
            this.records = records;
            useDocumentDragSource({
                ref: useRef("root"),
                elements: ".row",
                getList: () => ({
                    records,
                    selection: records.filter((record) => record.selected),
                }),
            });
        }
    }
    await mountWithCleanup(Rows);
}

describe("DocumentDragState", () => {
    test("the dragged rows fade at the start and come back at the end", () => {
        const drag = new DocumentDragState();
        const root = document.createElement("div");
        root.innerHTML = `<tr data-id="datapoint_1"></tr><tr data-id="datapoint_2"></tr>`;
        drag.start([makeRecord(1)], root);
        expect(drag.active).toBe(true);
        expect(drag.resIds).toEqual([1]);
        expect(root.querySelector("[data-id='datapoint_1']")).toHaveClass("opacity-50");
        expect(root.querySelector("[data-id='datapoint_2']")).not.toHaveClass("opacity-50");
        drag.over = 11;
        drag.end();
        expect(drag.active).toBe(false);
        expect(drag.over).toBe(null);
        expect(root.querySelector("[data-id='datapoint_1']")).not.toHaveClass("opacity-50");
    });
});

describe("the picture of the drag", () => {
    test("one file: its icon and name, as in the box of the selection of the core", () => {
        const ghost = makeDragGhost([makeRecord(3)]);
        expect(ghost.isConnected).toBe(true);
        expect(ghost.querySelector(".o_image").dataset.mimetype).toBe("audio/x-wav");
        expect(ghost.querySelector(".list-group-item.active")).toHaveText("file_3.wav");
        ghost.remove();
    });

    test("several files: the number, no name", () => {
        const ghost = makeDragGhost([makeRecord(1), makeRecord(2)]);
        expect(ghost.querySelector(".list-group-item.active")).toHaveText("2 documents");
        expect(ghost.querySelector("b")).toHaveText("2");
        ghost.remove();
    });

    test("its upper left corner is at the pointer", () => {
        const ghost = makeDragGhost([makeRecord(1)]);
        placeDragGhost(ghost, { x: 100, y: 50 });
        expect(ghost.style.transform).toBe("translate(100px, 50px)");
        ghost.remove();
    });
});

describe("useDocumentDragSource", () => {
    test("a row dragged to a folder is moved there", async () => {
        const { drag, calls } = await makeEnv();
        await mountRows([makeRecord(1), makeRecord(2)]);
        const { moveTo, drop } = await contains(".row:first-child").drag();
        expect(".o_int_filemanager_drag_ghost").toHaveCount(1);
        expect(".row:first-child").toHaveClass("opacity-50");
        expect(drag.resIds).toEqual([1]);
        await moveTo(".hallo");
        await animationFrame();
        expect(drag.over).toBe(11);
        await drop();
        await animationFrame();
        expect(calls).toEqual([
            ["write", "int.filemanager.document", [1], { folder_id: 11 }],
            ["notification", "Moved to Hallo"],
            ["doAction", "soft_reload"],
        ]);
        expect(".o_int_filemanager_drag_ghost").toHaveCount(0);
        expect(drag.active).toBe(false);
    });

    test("the ticked rows go together when one of them is dragged", async () => {
        const { drag, calls } = await makeEnv();
        await mountRows([
            makeRecord(1, { selected: true }),
            makeRecord(2, { selected: true }),
            makeRecord(3),
        ]);
        const { moveTo, drop } = await contains(".row:first-child").drag();
        expect(drag.resIds).toEqual([1, 2]);
        expect(".o_int_filemanager_drag_ghost").toHaveText("2 documents");
        await moveTo(".hallo");
        await drop();
        await animationFrame();
        expect(calls[0]).toEqual(["write", "int.filemanager.document", [1, 2], { folder_id: 11 }]);
    });

    test("a row that is not ticked goes alone, whatever is ticked", async () => {
        const { drag } = await makeEnv();
        await mountRows([makeRecord(1), makeRecord(2, { selected: true })]);
        const { cancel } = await contains(".row:first-child").drag();
        expect(drag.resIds).toEqual([1]);
        await cancel();
    });

    test("the folder that the documents are in is no target", async () => {
        const { drag, calls } = await makeEnv();
        await mountRows([makeRecord(1)]);
        const { moveTo, drop } = await contains(".row").drag();
        await moveTo(".root");
        await animationFrame();
        expect(drag.over).toBe(null);
        await drop();
        await animationFrame();
        expect(calls).toEqual([]);
    });

    test("a drag that ends outside of the panel moves nothing", async () => {
        const { drag, calls } = await makeEnv();
        await mountRows([makeRecord(1), makeRecord(2)]);
        const { moveTo, drop } = await contains(".row:first-child").drag();
        await moveTo(".row:last-child");
        await animationFrame();
        expect(drag.over).toBe(null);
        await drop();
        expect(calls).toEqual([]);
        expect(".o_int_filemanager_drag_ghost").toHaveCount(0);
    });

    test("a reader may not drag", async () => {
        const { drag } = await makeEnv({ canMove: false });
        await mountRows([makeRecord(1)]);
        await contains(".row").drag();
        expect(".o_int_filemanager_drag_ghost").toHaveCount(0);
        expect(drag.active).toBe(false);
    });

    test("a row in edition is not dragged", async () => {
        const { drag } = await makeEnv();
        await mountRows([makeRecord(1, { isInEdition: true })]);
        await contains(".row").drag();
        expect(drag.active).toBe(false);
    });
});

describe("useMoveDocuments", () => {
    test("writes the folder of the documents and reloads the view", async () => {
        const { calls } = await makeEnv();
        let move;
        class Moving extends Component {
            static template = xml`<div/>`;
            static props = {};
            setup() {
                move = useMoveDocuments();
            }
        }
        await mountWithCleanup(Moving);
        await move([5, 6], 11, "Hallo");
        expect(calls).toEqual([
            ["write", "int.filemanager.document", [5, 6], { folder_id: 11 }],
            ["notification", "Moved to Hallo"],
            ["doAction", "soft_reload"],
        ]);
    });
});
