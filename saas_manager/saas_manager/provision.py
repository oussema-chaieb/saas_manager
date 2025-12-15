import subprocess
import frappe

def provision_site(tenant_name):
    tenant = frappe.get_doc("SaaS Tenant", tenant_name)

    site_name = f"{tenant.subdomain}.local"

    try:
        tenant.status = "Provisioning"
        tenant.save()
        frappe.db.commit()

        subprocess.run([
            "bench", "new-site", site_name,
            "--admin-password", tenant.admin_password,
            "--no-mariadb-socket"
        ], check=True)

        subprocess.run([
            "bench", "--site", site_name,
            "install-app", "erpnext"
        ], check=True)

        tenant.status = "Active"
        tenant.save()
        frappe.db.commit()

    except Exception as e:
        tenant.status = "Failed"
        tenant.save()
        frappe.db.commit()
        raise e
