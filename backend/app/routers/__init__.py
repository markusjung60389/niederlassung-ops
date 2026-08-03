"""HTTP routers, one module per functional area."""

from . import (  # noqa: F401
    agent,
    assessments,
    audit,
    auth_routes,
    cockpit,
    compliance,
    fleet,
    incidents,
    personnel,
    sales,
)

ALL_ROUTERS = [
    auth_routes.router,
    cockpit.router,
    compliance.router,
    personnel.router,
    fleet.router,
    sales.router,
    incidents.router,
    assessments.router,
    audit.router,
    agent.router,
]
