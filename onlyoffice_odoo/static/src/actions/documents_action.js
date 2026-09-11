/** @odoo-module **/
import { cookie } from "@web/core/browser/cookie"
import { router } from "@web/core/browser/router"
import { rpc } from "@web/core/network/rpc"
import { registry } from "@web/core/registry"
import { useService } from "@web/core/utils/hooks"
const { Component, onMounted } = owl
export class DocumentsAction extends Component {
  setup() {
    super.setup()
    this.rpc = rpc
    this.orm = useService("orm")
    this.router = router
    onMounted(async () => {
      try {
        const args = {}
        if (this.props.action.params.document_id) {
          const document_id = this.props.action.params.document_id
          args.document_id = document_id
          this.router.pushState({ document_id: document_id })
        } else if (this.props.action.params.attachment_id) {
          const attachment_id = this.props.action.params.attachment_id
          args.attachment_id = attachment_id
          this.router.pushState({ attachment_id: attachment_id })
        }
        const response = await this.rpc("/onlyoffice/editor/get_config", args)
        const config = JSON.parse(response.editorConfig)
        const theme = cookie.get("color_scheme")
        config.editorConfig.customization = {
          ...config.editorConfig.customization,
          uiTheme: theme ? `default-${theme}` : "default-light",
        }
        this.config = config
        this.docApiJS = response.docApiJS
        if (!window.DocsAPI) {
          await this.loadDocsAPI(this.docApiJS)
        }
        if (window.DocsAPI) {
          window.docEditor = new DocsAPI.DocEditor("doceditor", this.config)
        } else {
          document.getElementById("error").classList.remove("d-none")
          throw new Error("window.DocsAPI is null")
        }
      } catch (error) {
        console.error("onMounted Editor error:", error)
        document.getElementById("error").classList.remove("d-none")
      }
    })
  }
  get backLabel() {
    // Statt fest "Zurück zum Auftrag" (nur fuer den urspruenglichen Reparaturauftrags-
    // Anwendungsfall geschrieben): Name des vorherigen Breadcrumb-Eintrags nehmen, damit die
    // Beschriftung passt, egal von wo aus der Editor geoeffnet wurde (Auftrag, Dateimanager,
    // ...). env.config.breadcrumbs traegt die aktuelle Aktion selbst als letzten Eintrag -
    // der vorletzte ist das Ziel von goBackToRecord() (window.history.back()). Kein Eintrag
    // vorhanden (z.B. Direktaufruf) -> generischer Fallback statt eines falschen Namens.
    const breadcrumbs = this.env.config?.breadcrumbs || []
    const previous = breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2] : null
    return previous && previous.name ? `Zurück zu ${previous.name}` : "Zurück"
  }
  goBackToRecord() {
    window.history.back()
  }
  async loadDocsAPI(DocsAPI) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script")
      script.src = DocsAPI
      script.onload = resolve
      script.onerror = reject
      document.body.appendChild(script)
      this.script = script
    })
  }
}
DocumentsAction.template = "onlyoffice_odoo.Editor"
registry.category("actions").add("onlyoffice_editor", DocumentsAction, { force: true })