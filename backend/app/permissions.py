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
# Group-wide rules: the catalogue, the functions and the compliance rules.
# A branch manager works inside them and may set an exception for their own
# branch; changing the rule itself is the area manager's.
RULE_READ = "rule:read"
RULE_WRITE = "rule:write"
BRANCH_READ = "branch:read"
BRANCH_WRITE = "branch:write"

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
    RULE_READ,
    RULE_WRITE,
    BRANCH_READ,
    BRANCH_WRITE,
)

READ_PERMISSIONS = tuple(item for item in ALL_PERMISSIONS if item.endswith(":read"))

ROLE_AREA_MANAGER = "Bereichsleiter"
ROLE_BRANCH_MANAGER = "Niederlassungsleiter"
ROLE_HSE = "HSE / Compliance"
ROLE_VIEWER = "Betrachter"

# name -> permissions. Applied on seed and kept in sync there, so a new
# permission reaches existing installations on restart.
#
# What a role may do is only half the answer: which branches it reaches is the
# other half and lives on the account (`users.all_branches`, `user_branches`).
# The branch manager holds every area permission but not RULE_WRITE - a
# group-wide rule reaches branches they are not responsible for. Setting an
# exception for their own branch is theirs and needs no approval; it is shown
# to the area manager, who can revoke it.
ROLE_PRESETS: dict[str, list[str]] = {
    ROLE_AREA_MANAGER: [WILDCARD],
    ROLE_BRANCH_MANAGER: [
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
        RULE_READ,
        BRANCH_READ,
    ],
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
        RULE_READ,
        BRANCH_READ,
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
