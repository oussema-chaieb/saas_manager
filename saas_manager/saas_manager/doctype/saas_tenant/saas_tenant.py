import os
import re
import subprocess
import frappe
from shutil import which
from frappe.model.document import Document

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$")


class SaaSTenant(Document):

    def validate(self):
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()

        if not self.status:
            self.status = "Draft"

        if not self.subdomain or not SUBDOMAIN_RE.match(self.subdomain):
            frappe.throw("Invalid subdomain. Use: a-z, 0-9, '-' (no spaces).")

        if frappe.db.exists("SaaS Tenant", {"subdomain": self.subdomain, "name": ["!=", self.name]}):
            frappe.throw("Subdomain already taken.")

    # ---------------------------
    # helpers
    # ---------------------------
    def _bench(self):
        bench = which("bench") or "/usr/local/bin/bench"
        if not os.path.exists(bench):
            frappe.throw(f"bench executable not found at: {bench}")

        env = os.environ.copy()
        env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")
        return bench, env

    def _run(self, cmd, cwd, env):
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
        if p.returncode != 0:
            msg = (
                f"CMD: {' '.join(cmd)}\n\n"
                f"STDOUT:\n{(p.stdout or '').strip()}\n\n"
                f"STDERR:\n{(p.stderr or '').strip()}"
            )
            self.db_set("last_error", msg[:14000])
            raise frappe.ValidationError((p.stderr or p.stdout or "bench failed").strip())
        return p

    # ---------------------------
    # public methods
    # ---------------------------
    @frappe.whitelist()
    def enqueue_provision(self):
        """Queue provisioning in background (long queue)"""
        frappe.only_for("System Manager")

        if self.status not in ("Draft", "Failed"):
            frappe.throw(f"Cannot provision in status: {self.status}")

        self.db_set("status", "Queued")
        self.db_set("last_error", None)

        frappe.enqueue(
            "saas_manager.saas_manager.doctype.saas_tenant.saas_tenant.run_provision_job",
            queue="long",
            tenant_name=self.name,
        )

        return {"tenant_id": self.name, "status": "Queued"}

    # ---------------------------
    # internal provisioning (called by worker)
    # ---------------------------
    def provision_site_internal(self):
        # domain
        base_domain = (self.base_domain or "local").strip().lower()
        site_name = f"{self.subdomain}.{base_domain}"

        self.db_set("status", "Provisioning")
        self.db_set("site_name", site_name)
        self.db_set("last_error", None)

        bench_path = frappe.utils.get_bench_path()
        cwd = bench_path
        bench, env = self._bench()

        admin_pwd = self.get_password("admin_password")

        # EXACT MATCH with your manual command
        db_root_user = "root"
        db_root_password = "admin"
        mariadb_scope = "%"

        # Apps to install at creation
        apps_to_install = ["erpnext"]  # add more if needed: ["erpnext", "print_designer"]

        cmd = [
            bench,
            "new-site",
            f"--mariadb-user-host-login-scope={mariadb_scope}",
            f"--admin-password={admin_pwd}",
            f"--db-root-username={db_root_user}",
            f"--db-root-password={db_root_password}",
        ]

        for app in apps_to_install:
            cmd += ["--install-app", app]

        cmd += [site_name]

        # Create site + install apps
        self._run(cmd, cwd=cwd, env=env)

        # Done
        self.db_set("status", "Active")
        self.db_set("site_url", f"https://{site_name}")

        return {"site_name": site_name, "site_url": f"https://{site_name}"}


def run_provision_job(tenant_name):
    """Background worker entrypoint"""
    tenant = frappe.get_doc("SaaS Tenant", tenant_name)
    try:
        tenant.provision_site_internal()
    except Exception as e:
        tenant.db_set("status", "Failed")
        # last_error is already set if bench failed, but keep safety
        if not tenant.last_error:
            tenant.db_set("last_error", str(e)[:14000])
        raise
