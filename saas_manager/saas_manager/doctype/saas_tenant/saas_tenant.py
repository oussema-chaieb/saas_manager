import os
import re
import subprocess
import frappe
from frappe.model.document import Document
from shutil import which

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$")


class SaaSTenant(Document):

    def validate(self):
        # Normalize
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()

        # Defaults
        if not self.status:
            self.status = "Draft"

        # Validate subdomain
        if not self.subdomain or not SUBDOMAIN_RE.match(self.subdomain):
            frappe.throw("Invalid subdomain. Use: a-z, 0-9, '-' (no spaces).")

        # Ensure uniqueness of subdomain
        if frappe.db.exists("SaaS Tenant", {"subdomain": self.subdomain, "name": ["!=", self.name]}):
            frappe.throw("Subdomain already taken.")

    def _get_bench_cmd_and_env(self):
        """
        Ensure we can execute bench from within gunicorn/worker environment.
        """
        bench = which("bench") or "/usr/local/bin/bench"

        if not os.path.exists(bench):
            frappe.throw(f"bench executable not found at: {bench}")

        env = os.environ.copy()
        # ensure /usr/local/bin is visible even if the worker PATH is restricted
        env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")

        return bench, env

    @frappe.whitelist()
    def provision_site(self):
        # Minimal security
        frappe.only_for("System Manager")

        if self.status not in ("Draft", "Failed"):
            frappe.throw(f"Cannot provision in status: {self.status}")

        # If base_domain is empty, default to "local"
        base_domain = (self.base_domain or "local").strip().lower()
        site_name = f"{self.subdomain}.{base_domain}"

        self.db_set("status", "Provisioning")
        self.db_set("site_name", site_name)

        bench_path = frappe.utils.get_bench_path()
        cwd = bench_path

        bench, env = self._get_bench_cmd_and_env()

        admin_pwd = self.get_password("admin_password")
        db_name = f"site_{self.subdomain}".replace("-", "_")

        try:
            # 1) Create site
            subprocess.run(
                [
                    bench, "new-site", site_name,
                    "--admin-password", admin_pwd,
                    "--db-name", db_name,
                    "--no-mariadb-socket"
                ],
                check=True,
                cwd=cwd,
                env=env
            )

            # 2) Install apps
            subprocess.run(
                [bench, "--site", site_name, "install-app", "erpnext"],
                check=True,
                cwd=cwd,
                env=env
            )

            # ✅ install your tunisian app if needed
            # subprocess.run(
            #     [bench, "--site", site_name, "install-app", "tunisia_localisation"],
            #     check=True,
            #     cwd=cwd,
            #     env=env
            # )

            self.db_set("status", "Active")
            self.db_set("site_url", f"http://{site_name}")

            return {"site_name": site_name, "site_url": f"http://{site_name}"}

        except Exception as e:
            self.db_set("status", "Failed")
            self.db_set("last_error", str(e))
            raise
