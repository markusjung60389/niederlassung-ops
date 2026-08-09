"""HTTP routers, one module per functional area."""

from . import (  # noqa: F401
    agent,
    assessments,
    audit,
    auth_routes,
    branches,
    catalog_routes,
    cockpit,
    compliance,
    compliance_rules,
    fleet,
    incidents,
    personnel,
    sales,
    salary,
    users,
)

ALL_ROUTERS = [
    auth_routes.router,
    branches.router,
    cockpit.router,
    compliance.router,
    compliance_rules.router,
    personnel.router,
    catalog_routes.router,
    fleet.router,
    sales.router,
    incidents.router,
    assessments.router,
    audit.router,
    agent.router,
    users.router,
    salary.router,
]
