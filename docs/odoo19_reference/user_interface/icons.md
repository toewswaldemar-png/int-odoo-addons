<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/user_interface/icons.html · abgerufen 2026-10-02 -->

# UI icons

Odoo’s user interface mostly relies on [FontAwesome4 icons](https://fontawesome.com/v4/icons/).

To cover FontAwesome’s lack of iconography for specific functionalities, we designed our own
icons: Odoo UI icons and Odoo Spreadsheet icons.

## Odoo UI icons

The Odoo UI icons can be rendered using the main `oi` class in conjunction with the specific icon
class.

> **Example**
>
> ```html
> <i class="oi oi-odoo"/>
> ```

`oi-odoo`
`oi-view`
`oi-view-kanban`
`oi-view-list`
`oi-view-cohort`
`oi-view-pivot`
`oi-text-break`
`oi-text-inline`
`oi-text-wrap`
`oi-text-effect`
`oi-search`
`oi-group`
`oi-settings-adjust`
`oi-panel-right`
`oi-launch`
`oi-apps`
`oi-studio`
`oi-voip`
`oi-gif-picker`
`oi-close`
`oi-chevron-down`
`oi-chevron-left`
`oi-chevron-right`
`oi-chevron-up`
`oi-arrows-h`
`oi-arrows-v`
`oi-arrow-down-left`
`oi-arrow-down-right`
`oi-arrow-down`
`oi-arrow-left`
`oi-arrow-right`
`oi-arrow-up-left`
`oi-arrow-up-right`
`oi-arrow-up`
`oi-draggable`
`oi-archive`
`oi-unarchive`
`oi-smile-add`
`oi-close`
`oi-food-delivery`
`oi-activity`
`oi-activity-plus`
`oi-schedule-today`
`oi-schedule-tomorrow`
`oi-schedule-later`
`oi-backspace-o`
`oi-numpad`
`oi-record`
`oi-merge`
`oi-transfer`
`oi-suitcase`
`oi-suitcase-plus`
`oi-user`
`oi-user-plus`
`oi-users`
`oi-ellipsis-v`
`oi-ellipsis-h`
`oi-plus`
`oi-minus`
`oi-star-plus`
`oi-subtitle`
`oi-bluesky`
`oi-tiktok`
`oi-discord`
`oi-google-play`
`oi-kickstarter`
`oi-strava`
`oi-threads`
`oi-x`
`oi-x-square`

### RTL adaptations

Directional icons have RTL adaptations which flip the icons by 180 degrees
when an RTL language is selected.

`oi-chevron-left`
`oi-chevron-right`
`oi-arrow-down-left`
`oi-arrow-down-right`
`oi-arrow-left`
`oi-arrow-right`
`oi-arrow-up-left`
`oi-arrow-up-right`

## Odoo Spreadsheet icons

The [Odoo Spreadsheet](https://github.com/odoo/odoo/blob/19.0/addons/spreadsheet/static/src/o_spreadsheet) icons are
defined as `<svg>` elements and rendered using QWeb [templates](https://github.com/odoo/owl/blob/master/doc/v2/reference/templates.md).

> **Example**
>
> ```html
> <t t-name="o-spreadsheet-Icon.GLOBAL_FILTERS">
>     <svg width="20" height="20" viewbox="0 0 20 20">
>         <path fill="currentColor" d="M1 3h12L7 9M5.5 6h3v11l-3-3M14 4h4v2h-4m-3 3h7v2h-7m0 3h7v2h-7"/>
>     </svg>
> </t>
> ```

`SEE_RECORDS`

`GLOBAL_FILTERS`

`NEW`

`COPY_FILE`

`SAVE`

`VERSION_HISTORY`

`CAMERA`

`DOWNLOAD_AS_JSON`

`ADD_TO_DASHBOARD`

`ODOO_LIST`

`INSERT_LIST`

`REFRESH_DATA`

`COMMENTS`

`LINE_CHART`

`STACKED_LINE_CHART`

`AREA_CHART`

`STACKED_AREA_CHART`

`COLUMN_CHART`

`STACKED_COLUMN_CHART`

`BAR_CHART`

`STACKED_BAR_CHART`

`COMBO_CHART`

`PIE_CHART`

`DOUGHNUT_CHART`

`SCATTER_CHART`

`GAUGE_CHART`

`SCORECARD_CHART`

`WATERFALL_CHART`

`POPULATION_PYRAMID_CHART`

`RADAR_CHART`

`FILLED_RADAR_CHART`

`GEO_CHART`

`FUNNEL_CHART`

`SUNBURST_CHART`

`TREE_MAP_CHART`

`CLEAR_AND_RELOAD`

`EXPORT_XLSX`

`OPEN_READ_ONLY`

`OPEN_DASHBOARD`

`OPEN_READ_WRITE`

`IMPORT_XLSX`

`UNDO`

`REDO`

`CUT`

`COPY_AS_IMAGE`

`PASTE`

`CLEAR`

`FREEZE`

`UNFREEZE`

`FORMULA`

`HIDE_ROW`

`UNHIDE_ROW`

`HIDE_COL`

`UNHIDE_COL`

`INSERT_ROW`

`INSERT_ROW_BEFORE`

`INSERT_ROW_AFTER`

`INSERT_COL`

`INSERT_COL_AFTER`

`INSERT_COL_BEFORE`

`INSERT_CELL`

`INSERT_CELL_SHIFT_DOWN`

`INSERT_CELL_SHIFT_RIGHT`

`DELETE_CELL_SHIFT_UP`

`DELETE_CELL_SHIFT_LEFT`

`INSERT_DROPDOWN`

`INSERT_SHEET`

`PAINT_FORMAT`

`CONDITIONAL_FORMAT`

`CLEAR_FORMAT`

`BOLD`

`ITALIC`

`UNDERLINE`

`STRIKE`

`TEXT_COLOR`

`FILL_COLOR`

`MERGE_CELL`

`ALIGN_LEFT`

`ALIGN_CENTER`

`ALIGN_RIGHT`

`ALIGN_TOP`

`ALIGN_MIDDLE`

`ALIGN_BOTTOM`

`WRAPPING_OVERFLOW`

`WRAPPING_WRAP`

`WRAPPING_CLIP`

`BORDERS`

`BORDER_HV`

`BORDER_H`

`BORDER_V`

`BORDER_EXTERNAL`

`BORDER_LEFT`

`BORDER_TOP`

`BORDER_RIGHT`

`BORDER_BOTTOM`

`BORDER_CLEAR`

`BORDER_TYPE`

`BORDER_COLOR`

`BORDER_NO_COLOR`

`PLUS`

`MINUS`

`LIST`

`ARROW_DOWN`

`ARROW_UP`

`ARROW_RIGHT`

`SMILE`

`MEH`

`FROWN`

`GREEN_DOT`

`YELLOW_DOT`

`RED_DOT`

`SMALL_DOT_RIGHT_ALIGN`

`SORT_RANGE`

`FILTER_ICON`

`CHECK`

`NUMBER_FORMATS`

`FONT_SIZE`

`SPLIT_TEXT`

`DISPLAY_HEADER`

`COG`

`PLUS_IN_BOX`

`MINUS_IN_BOX`

`GROUP_ROWS`

`UNGROUP_ROWS`

`GROUP_COLUMNS`

`UNGROUP_COLUMNS`

`DATA_VALIDATION`

`THIN_DRAG_HANDLE`

`SHORT_THIN_DRAG_HANDLE`

`EDIT_TABLE`

`DELETE_TABLE`

`PAINT_TABLE`

`CIRCLE_INFO`

`PIVOT`

`INSERT_PIVOT`

`MOVE_SHEET_LEFT`

`MOVE_SHEET_RIGHT`

`RENAME_SHEET`

`CAROUSEL`
