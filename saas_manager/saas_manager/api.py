import re
import frappe

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$")


@frappe.whitelist(allow_guest=True)
def create_tenant(company_name, email, subdomain, admin_password):
    """
    Public SaaS API:
    - creates SaaS Tenant doc
    - enqueues provisioning
    - returns tenant_id immediately
    """

    frappe.rate_limiter(limit=5, seconds=60)

    subdomain = (subdomain or "").strip().lower()
    if not SUBDOMAIN_RE.match(subdomain):
        frappe.throw("Invalid subdomain")

    # Create SaaS Tenant
    tenant = frappe.get_doc({
        "doctype": "SaaS Tenant",
        "company_name": company_name,
        "subdomain": subdomain,
        "admin_password": admin_password,
        "status": "Draft",
        "email": email,
    })
    tenant.insert(ignore_permissions=True)

    # enqueue
    tenant.enqueue_provision()

    return {
        "tenant_id": tenant.name,
        "status": tenant.status
    }


@frappe.whitelist(allow_guest=True)
def tenant_status(tenant_id):
    tenant = frappe.get_doc("SaaS Tenant", tenant_id)
    return {
        "tenant_id": tenant.name,
        "status": tenant.status,
        "site_url": tenant.site_url,
        "site_name": tenant.site_name,
        "last_error": tenant.last_error,
    }
