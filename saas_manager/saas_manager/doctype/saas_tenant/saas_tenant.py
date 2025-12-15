import os
import re
import subprocess
import frappe
from frappe.model.document import Document

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$")

class SaaSTenant(Document):

    def validate(self):
        # Normalise
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()

        # Defaults
        if not self.status:
            self.status = "Draft"

        # Validation subdomain
        if not self.subdomain or not SUBDOMAIN_RE.match(self.subdomain):
            frappe.throw("Invalid subdomain. Use: a-z, 0-9, '-' (no spaces).")

        # Unicité subdomain
        if frappe.db.exists("SaaS Tenant", {"subdomain": self.subdomain, "name": ["!=", self.name]}):
            frappe.throw("Subdomain already taken.")

    @frappe.whitelist()
    def provision_site(self):
        # Sécurité minimale
        frappe.only_for("System Manager")

        if self.status not in ("Draft", "Failed"):
            frappe.throw(f"Cannot provision in status: {self.status}")

        base_domain = (self.base_domain or "local").strip().lower()
        site_name = f"{self.subdomain}.{base_domain}"

        self.db_set("status", "Provisioning")
        self.db_set("site_name", site_name)

        bench_path = frappe.utils.get_bench_path()
        bench = os.path.join(bench_path, "bench")  # ex: /home/frappe/frappe-bench/bench
        cwd = bench_path

        admin_pwd = self.get_password("admin_password")  # Password field in DocType
        db_name = f"site_{self.subdomain}".replace("-", "_")

        try:
            # 1) create site
            subprocess.run(
                [bench, "new-site", site_name,
                 "--admin-password", admin_pwd,
                 "--db-name", db_name,
                 "--no-mariadb-socket"],
                check=True,
                cwd=cwd
            )

            # 2) install apps
            subprocess.run([bench, "--site", site_name, "install-app", "erpnext"], check=True, cwd=cwd)

            # ✅ installe ton app tunisienne ici (change le nom)
            # subprocess.run([bench, "--site", site_name, "install-app", "tunisia_localisation"], check=True, cwd=cwd)

            self.db_set("status", "Active")
            self.db_set("site_url", f"http://{site_name}")

            return {"site_name": site_name, "site_url": f"http://{site_name}"}

        except Exception as e:
            self.db_set("status", "Failed")
            self.db_set("last_error", str(e))
            raise
