"""Accounts, opportunities, projects and service contracts.

These tables existed from the start but had no API, which is why the cockpit
tiles "Pipeline EUR" and "Service due" could only ever show zero.
"""

from .. import crud, models, permissions, schemas
from fastapi import APIRouter

router = APIRouter(tags=["sales"])

crud.register(
    router,
    "/api/accounts",
    crud.Crud(
        model=models.Account,
        create_schema=schemas.AccountCreate,
        update_schema=schemas.AccountUpdate,
        read_schema=schemas.AccountRead,
        entity_type="account",
        label="Account",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"branch_id": models.Branch, "owner_user_id": models.User},
        filters={"branch_id": "branch_id", "account_type": "account_type"},
        order_by="name",
        children=[
            (models.Opportunity, "account_id", "opportunity/opportunities"),
            (models.ServiceContract, "account_id", "service contract(s)"),
            (models.Project, "account_id", "project(s)"),
        ],
    ),
)

crud.register(
    router,
    "/api/opportunities",
    crud.Crud(
        model=models.Opportunity,
        create_schema=schemas.OpportunityCreate,
        update_schema=schemas.OpportunityUpdate,
        read_schema=schemas.OpportunityRead,
        entity_type="opportunity",
        label="Opportunity",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"account_id": models.Account, "owner_user_id": models.User},
        filters={"account_id": "account_id", "offer_status": "offer_status"},
        order_by="follow_up_date",
    ),
)

crud.register(
    router,
    "/api/projects",
    crud.Crud(
        model=models.Project,
        create_schema=schemas.ProjectCreate,
        update_schema=schemas.ProjectUpdate,
        read_schema=schemas.ProjectRead,
        entity_type="project",
        label="Project",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"account_id": models.Account},
        filters={"account_id": "account_id", "status": "status"},
        order_by="name",
        children=[
            (models.ProjectSite, "project_id", "site(s)"),
            (models.Incident, "project_id", "incident(s)"),
            (models.ComplianceEvidence, "linked_project_id", "linked evidence item(s)"),
        ],
    ),
)

crud.register(
    router,
    "/api/project-sites",
    crud.Crud(
        model=models.ProjectSite,
        create_schema=schemas.ProjectSiteCreate,
        update_schema=schemas.ProjectSiteUpdate,
        read_schema=schemas.ProjectSiteRead,
        entity_type="project_site",
        label="Project site",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"project_id": models.Project},
        filters={"project_id": "project_id"},
        order_by="name",
        children=[(models.Incident, "site_id", "incident(s)")],
    ),
)

crud.register(
    router,
    "/api/service-contracts",
    crud.Crud(
        model=models.ServiceContract,
        create_schema=schemas.ServiceContractCreate,
        update_schema=schemas.ServiceContractUpdate,
        read_schema=schemas.ServiceContractRead,
        entity_type="service_contract",
        label="Service contract",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"account_id": models.Account},
        filters={"account_id": "account_id"},
        order_by="next_maintenance_at",
        children=[(models.ServiceEvent, "service_contract_id", "service event(s)")],
    ),
)

crud.register(
    router,
    "/api/service-events",
    crud.Crud(
        model=models.ServiceEvent,
        create_schema=schemas.ServiceEventCreate,
        update_schema=schemas.ServiceEventUpdate,
        read_schema=schemas.ServiceEventRead,
        entity_type="service_event",
        label="Service event",
        read_permission=permissions.SALES_READ,
        write_permission=permissions.SALES_WRITE,
        references={"service_contract_id": models.ServiceContract},
        filters={"service_contract_id": "service_contract_id", "event_type": "event_type"},
        order_by="scheduled_at",
        order_desc=True,
    ),
)

crud.register(
    router,
    "/api/tasks",
    crud.Crud(
        model=models.Task,
        create_schema=schemas.TaskCreate,
        update_schema=schemas.TaskUpdate,
        read_schema=schemas.TaskRead,
        entity_type="task",
        label="Task",
        read_permission=permissions.COMPLIANCE_READ,
        write_permission=permissions.COMPLIANCE_WRITE,
        references={"owner_user_id": models.User},
        filters={"status": "status", "owner_user_id": "owner_user_id", "source_type": "source_type"},
        order_by="due_date",
    ),
)
