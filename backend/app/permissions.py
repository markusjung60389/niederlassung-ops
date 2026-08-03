"""Permission catalogue and the role presets seeded into the roles table.

Kept free of FastAPI and SQLAlchemy imports so it can be used by the seed, the
auth layer and the tests without pulling in the whole application.
"""

WILDCARD = "*"

COMPLIANCE_READ = "compliance:read"
COMPLIANCE_WRITE = "compliance:write"
PERSONNEL_READ = "personnel:read"
PERSONNEL_WRITE = "personnel:write"
FLEET_READ = "fleet:read"
FLEET_WRITE = "fleet:write"
SALES_READ = "sales:read"
SALES_WRITE = "sales:write"
ASSESSMENT_READ = "assessment:read"
ASSESSMENT_WRITE = "assessment:write"
INCIDENT_READ = "incident:read"
INCIDENT_WRITE = "incident:write"
AGENT_RUN = "agent:run"
AUDIT_READ = "audit:read"

ALL_PERMISSIONS = (
    COMPLIANCE_READ,
    COMPLIANCE_WRITE,
    PERSONNEL_READ,
    PERSONNEL_WRITE,
    FLEET_READ,
    FLEET_WRITE,
    SALES_READ,
    SALES_WRITE,
    ASSESSMENT_READ,
    ASSESSMENT_WRITE,
    INCIDENT_READ,
    INCIDENT_WRITE,
    AGENT_RUN,
    AUDIT_READ,
)

READ_PERMISSIONS = tuple(item for item in ALL_PERMISSIONS if item.endswith(":read"))

ROLE_BRANCH_MANAGER = "Niederlassungsleiter"
ROLE_HSE = "HSE / Compliance"
ROLE_VIEWER = "Betrachter"

# name -> permissions. Applied on seed; existing rows are not overwritten.
ROLE_PRESETS: dict[str, list[str]] = {
    ROLE_BRANCH_MANAGER: [WILDCARD],
    ROLE_HSE: [
        COMPLIANCE_READ,
        COMPLIANCE_WRITE,
        INCIDENT_READ,
        INCIDENT_WRITE,
        PERSONNEL_READ,
        FLEET_READ,
        ASSESSMENT_READ,
        SALES_READ,
        AGENT_RUN,
        AUDIT_READ,
    ],
    ROLE_VIEWER: list(READ_PERMISSIONS),
}


def grants(held: object, required: str) -> bool:
    """True when the held permission collection satisfies `required`.

    Supports the wildcard `*` and per-area wildcards such as `compliance:*`.
    """
    if not held:
        return False
    held_set = {str(item) for item in held}
    if WILDCARD in held_set or required in held_set:
        return True
    area = required.split(":", 1)[0]
    return f"{area}:{WILDCARD}" in held_set
