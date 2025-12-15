frappe.ui.form.on("SaaS Tenant", {
  refresh(frm) {
    if (["Draft", "Failed"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Provision Site"), () => {
        frm.call({
          method: "provision_site",
          doc: frm.doc,
          freeze: true,
          freeze_message: __("Creating ERPNext site...")
        }).then((r) => {
          frm.reload_doc();
          if (r && r.message && r.message.site_url) {
            frappe.msgprint(__("Created: ") + r.message.site_url);
          }
        });
      });
    }

    if (frm.doc.site_url && frm.doc.status === "Active") {
      frm.add_custom_button(__("Open Site"), () => {
        window.open(frm.doc.site_url, "_blank");
      });
    }
  }
});
