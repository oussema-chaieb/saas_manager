frappe.ui.form.on("SaaS Tenant", {
  refresh(frm) {

    // Queue provisioning (recommended SaaS way)
    if (["Draft", "Failed"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Queue Provision"), () => {
        frm.call({
          method: "enqueue_provision",
          doc: frm.doc,
          freeze: true,
          freeze_message: __("Queued provisioning...")
        }).then(() => frm.reload_doc());
      });
    }

    // Open site when ready
    if (frm.doc.site_url && frm.doc.status === "Active") {
      frm.add_custom_button(__("Open Site"), () => {
        window.open(frm.doc.site_url, "_blank");
      });
    }
  }
});
