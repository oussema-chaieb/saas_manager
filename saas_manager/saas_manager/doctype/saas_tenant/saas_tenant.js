// Copyright (c) 2025, DON and contributors
// For license information, please see license.txt

frappe.ui.form.on('SaaS Tenant', {
    refresh(frm) {
        if (frm.doc.status === "Draft") {
            frm.add_custom_button("Provision Site", () => {
                frappe.call({
                    method: "saas_manager.provision.provision_site",
                    args: {
                        tenant_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: "Creating ERPNext site..."
                });
            });
        }
    }
});
